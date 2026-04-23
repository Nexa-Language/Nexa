"""
Nexa Database Integration — 内置数据库运行时引擎

核心概念：
- 连接注册表: 全局 Dict[int, DatabaseConnection] 管理所有活跃连接
- NexaSQLite: Python sqlite3 标准库实现，零额外依赖
- NexaPostgres: psycopg2 可选依赖实现
- 统一接口: query/query_one/execute/close/begin/commit/rollback 自动检测连接类型
- 类型转换: Python ↔ SQL 双向转换 (None→NULL, bool→INTEGER(0/1), etc.)
- 参数占位符适配: SQLite ? vs PostgreSQL $1,$2...
- 契约联动: DB 连接失败 → 500, 查询参数错误 → 400
- Agent 记忆接口: agent_memory_query/agent_memory_store 简化键值存储

Nexa 特色：
- Agent-DB 融合: Agent 可直接使用数据库作为长期记忆后端
- 契约联动: requires/ensures 断言与数据库操作联动
- DB DSL: 声明式数据库连接声明而非纯函数调用
"""

import sqlite3
import json
import threading
from typing import Any, Dict, List, Optional, Tuple

from .contracts import ContractViolation

# ==================== 连接注册表 ====================

_connection_registry: Dict[int, Any] = {}
_transaction_registry: Dict[int, bool] = {}  # conn_id → in_transaction
_connection_id_counter: int = 0
_registry_lock = threading.Lock()


def _next_connection_id() -> int:
    """生成下一个连接 ID (线程安全)"""
    global _connection_id_counter
    with _registry_lock:
        _connection_id_counter += 1
        return _connection_id_counter


def _register_connection(conn_id: int, connection: Any) -> None:
    """注册连接到全局注册表"""
    with _registry_lock:
        _connection_registry[conn_id] = connection
        _transaction_registry[conn_id] = False


def _unregister_connection(conn_id: int) -> None:
    """从全局注册表移除连接"""
    with _registry_lock:
        _connection_registry.pop(conn_id, None)
        _transaction_registry.pop(conn_id, None)


def _get_connection(conn_id: int) -> Any:
    """从全局注册表获取连接"""
    with _registry_lock:
        return _connection_registry.get(conn_id)


def get_active_connections() -> Dict[int, Any]:
    """获取所有活跃连接的快照"""
    with _registry_lock:
        return dict(_connection_registry)


# ==================== 类型转换 ====================

def python_to_sql(value: Any) -> Any:
    """将 Python 值转换为 SQL 兼容值

    转换规则:
    - None → NULL (None)
    - bool → INTEGER (True=1, False=0)
    - int → INTEGER (原值)
    - float → REAL (原值)
    - str → TEXT (原值)
    - list → TEXT (JSON 序列化)
    - dict → TEXT (JSON 序列化)
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    # 其他类型尝试转为字符串
    return str(value)


def sql_to_python(value: Any, col_type: Optional[str] = None) -> Any:
    """将 SQL 值转换为 Python 值

    转换规则:
    - NULL → None
    - INTEGER → int (0 → False, 1 → True 如果 col_type 提示为 bool)
    - REAL → float
    - TEXT → str (尝试 JSON 反序列化)
    """
    if value is None:
        return None
    if isinstance(value, int):
        # 如果列类型提示为布尔，将 0/1 映射为 False/True
        if col_type and col_type.upper() == "BOOL":
            return bool(value)
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        # 尝试 JSON 反序列化
        if value.startswith("{") or value.startswith("["):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value
        return value
    if isinstance(value, bytes):
        # BLOB 类型: 尝试解码为字符串
        try:
            return value.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            return value
    return value


# ==================== 参数占位符适配 ====================

def adapt_sql_params(sql: str, params: List[Any], db_type: str) -> Tuple[str, List[Any]]:
    """适配 SQL 参数占位符

    SQLite 使用 ? 占位符，PostgreSQL 使用 $1, $2... 占位符。
    此函数将 ? 占位符转换为 PostgreSQL 的 $N 格式，
    或将 $N 格式转换为 SQLite 的 ? 格式。

    Args:
        sql: SQL 语句
        params: 参数列表
        db_type: 'sqlite' 或 'postgres'

    Returns:
        (适配后的 SQL, 适配后的参数列表)
    """
    if db_type == "postgres":
        # 将 ? 替换为 $1, $2, $3...
        result_sql = sql
        param_idx = 1
        while "?" in result_sql:
            result_sql = result_sql.replace("?", f"${param_idx}", 1)
            param_idx += 1
        return result_sql, params
    elif db_type == "sqlite":
        # 将 $1, $2... 替换为 ?
        import re
        result_sql = re.sub(r"\$\d+", "?", sql)
        # 按参数编号排序参数
        if "$" in sql:
            matches = re.findall(r"\$(\d+)", sql)
            if matches:
                indices = [int(m) - 1 for m in sorted(set(matches), key=int)]
                sorted_params = [params[i] if i < len(params) else None for i in indices]
                return result_sql, sorted_params
        return result_sql, params
    else:
        return sql, params


# ==================== 连接句柄 ====================

def _make_handle(conn_id: int, db_type: str) -> Dict[str, Any]:
    """创建连接句柄字典

    格式: {"_nexa_db_connection_id": int, "db_type": str, "connected": bool}
    """
    return {
        "_nexa_db_connection_id": conn_id,
        "db_type": db_type,
        "connected": True,
    }


def _is_valid_handle(handle: Dict[str, Any]) -> bool:
    """验证连接句柄是否有效"""
    if not isinstance(handle, dict):
        return False
    if "_nexa_db_connection_id" not in handle:
        return False
    if "db_type" not in handle:
        return False
    if not handle.get("connected", False):
        return False
    return True


def _get_db_type_from_handle(handle: Dict[str, Any]) -> str:
    """从连接句柄获取数据库类型"""
    return handle.get("db_type", "sqlite")


def _get_conn_id_from_handle(handle: Dict[str, Any]) -> int:
    """从连接句柄获取连接 ID"""
    return handle.get("_nexa_db_connection_id", -1)


# ==================== NexaSQLite ====================

class NexaSQLite:
    """SQLite 数据库连接管理器

    使用 Python sqlite3 标准库，零额外依赖。
    自动启用 WAL 模式和外键约束。
    """

    @staticmethod
    def connect(path: str = ":memory:") -> Dict[str, Any]:
        """连接 SQLite 数据库

        Args:
            path: 数据库文件路径，":memory:" 表示内存数据库

        Returns:
            连接句柄字典

        Raises:
            ContractViolation: 连接失败时抛出 (映射为 500 Internal Server Error)
        """
        try:
            # 解析路径: 支持 "sqlite://path" 格式
            actual_path = path
            if path.startswith("sqlite://"):
                actual_path = path[len("sqlite://"):]

            conn = sqlite3.connect(actual_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # 启用行工厂以返回字典

            # 自动启用 WAL 模式 (Write-Ahead Logging)
            conn.execute("PRAGMA journal_mode=WAL")

            # 自动启用外键约束
            conn.execute("PRAGMA foreign_keys=ON")

            conn_id = _next_connection_id()
            _register_connection(conn_id, conn)

            return _make_handle(conn_id, "sqlite")

        except Exception as e:
            raise ContractViolation(
                message=f"SQLite connection failed: {e}",
                clause_type="requires",
                context={"path": path, "error": str(e)},
            )

    @staticmethod
    def query(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """查询所有行，返回 List[Dict]

        Args:
            handle: 连接句柄
            sql: SQL 查询语句 (使用 ? 占位符)
            params: 参数列表

        Returns:
            每行一个字典的列表

        Raises:
            ContractViolation: 查询参数错误 (映射为 400 Bad Request)
        """
        if not _is_valid_handle(handle):
            raise ContractViolation(
                message="Invalid or disconnected database handle",
                clause_type="requires",
                context={"handle": handle},
            )

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is None:
            raise ContractViolation(
                message=f"Connection {conn_id} not found in registry",
                clause_type="requires",
                context={"conn_id": conn_id},
            )

        try:
            adapted_params = [python_to_sql(p) for p in (params or [])]
            cursor = conn.execute(sql, adapted_params)
            rows = cursor.fetchall()
            result = []
            for row in rows:
                row_dict = {}
                for idx, col_desc in enumerate(cursor.description):
                    col_name = col_desc[0]  # description is tuple: (name, type_code, ...)
                    val = row[idx]
                    row_dict[col_name] = sql_to_python(val)
                result.append(row_dict)
            return result

        except Exception as e:
            raise ContractViolation(
                message=f"SQLite query failed: {e}",
                clause_type="requires",
                context={"sql": sql, "params": params, "error": str(e)},
            )

    @staticmethod
    def query_one(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
        """查询单行，返回 Optional[Dict]

        Args:
            handle: 连接句柄
            sql: SQL 查询语句 (使用 ? 占位符)
            params: 参数列表

        Returns:
            单行字典或 None
        """
        results = NexaSQLite.query(handle, sql, params)
        if results:
            return results[0]
        return None

    @staticmethod
    def execute(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> int:
        """执行写操作，返回受影响行数

        Args:
            handle: 连接句柄
            sql: SQL 语句 (使用 ? 占位符)
            params: 参数列表

        Returns:
            受影响的行数

        Raises:
            ContractViolation: 查询参数错误 (映射为 400 Bad Request)
        """
        if not _is_valid_handle(handle):
            raise ContractViolation(
                message="Invalid or disconnected database handle",
                clause_type="requires",
                context={"handle": handle},
            )

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is None:
            raise ContractViolation(
                message=f"Connection {conn_id} not found in registry",
                clause_type="requires",
                context={"conn_id": conn_id},
            )

        try:
            adapted_params = [python_to_sql(p) for p in (params or [])]
            cursor = conn.execute(sql, adapted_params)
            # Only auto-commit if not in an explicit transaction
            in_txn = _transaction_registry.get(conn_id, False)
            if not in_txn:
                conn.commit()
            return cursor.rowcount

        except Exception as e:
            raise ContractViolation(
                message=f"SQLite execute failed: {e}",
                clause_type="requires",
                context={"sql": sql, "params": params, "error": str(e)},
            )

    @staticmethod
    def close(handle: Dict[str, Any]) -> bool:
        """关闭连接，从注册表移除

        Args:
            handle: 连接句柄

        Returns:
            True 如果成功关闭
        """
        if not isinstance(handle, dict):
            return False

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            _unregister_connection(conn_id)

        # 标记句柄为断开
        handle["connected"] = False
        return True

    @staticmethod
    def begin(handle: Dict[str, Any]) -> Dict[str, Any]:
        """开始事务

        Args:
            handle: 连接句柄

        Returns:
            更新后的连接句柄
        """
        if not _is_valid_handle(handle):
            raise ContractViolation(
                message="Invalid or disconnected database handle",
                clause_type="requires",
                context={"handle": handle},
            )

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is None:
            raise ContractViolation(
                message=f"Connection {conn_id} not found in registry",
                clause_type="requires",
                context={"conn_id": conn_id},
            )

        try:
            _transaction_registry[conn_id] = True
            conn.execute("BEGIN")
            return handle
        except Exception as e:
            raise ContractViolation(
                message=f"SQLite begin transaction failed: {e}",
                clause_type="requires",
                context={"error": str(e)},
            )

    @staticmethod
    def commit(handle: Dict[str, Any]) -> bool:
        """提交事务

        Args:
            handle: 连接句柄

        Returns:
            True 如果提交成功
        """
        if not _is_valid_handle(handle):
            raise ContractViolation(
                message="Invalid or disconnected database handle",
                clause_type="requires",
                context={"handle": handle},
            )

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is None:
            raise ContractViolation(
                message=f"Connection {conn_id} not found in registry",
                clause_type="requires",
                context={"conn_id": conn_id},
            )

        try:
            conn.commit()
            _transaction_registry[conn_id] = False
            return True
        except Exception as e:
            raise ContractViolation(
                message=f"SQLite commit failed: {e}",
                clause_type="requires",
                context={"error": str(e)},
            )

    @staticmethod
    def rollback(handle: Dict[str, Any]) -> bool:
        """回滚事务

        Args:
            handle: 连接句柄

        Returns:
            True 如果回滚成功
        """
        if not _is_valid_handle(handle):
            raise ContractViolation(
                message="Invalid or disconnected database handle",
                clause_type="requires",
                context={"handle": handle},
            )

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is None:
            raise ContractViolation(
                message=f"Connection {conn_id} not found in registry",
                clause_type="requires",
                context={"conn_id": conn_id},
            )

        try:
            conn.rollback()
            _transaction_registry[conn_id] = False
            return True
        except Exception as e:
            raise ContractViolation(
                message=f"SQLite rollback failed: {e}",
                clause_type="requires",
                context={"error": str(e)},
            )


# ==================== NexaPostgres ====================

try:
    import psycopg2
    import psycopg2.extras
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False


class NexaPostgres:
    """PostgreSQL 数据库连接管理器

    使用 psycopg2 (可选依赖)。如果 psycopg2 不可安装，
    此类仍然定义但 connect() 会抛出 ImportError。
    """

    @staticmethod
    def connect(url: str) -> Dict[str, Any]:
        """连接 PostgreSQL 数据库

        Args:
            url: PostgreSQL 连接串 (postgres://host/db 或完整 URL)

        Returns:
            连接句柄字典

        Raises:
            ImportError: psycopg2 未安装
            ContractViolation: 连接失败 (映射为 500 Internal Server Error)
        """
        if not _PSYCOPG2_AVAILABLE:
            raise ImportError(
                "psycopg2 is not installed. Install it with: pip install psycopg2-binary"
            )

        try:
            # 解析 URL: 支持 "postgres://..." 和 "postgresql://..." 格式
            actual_url = url
            if url.startswith("postgresql://"):
                actual_url = url
            elif url.startswith("postgres://"):
                actual_url = url

            conn = psycopg2.connect(actual_url)
            conn.autocommit = False

            conn_id = _next_connection_id()
            _register_connection(conn_id, conn)

            return _make_handle(conn_id, "postgres")

        except Exception as e:
            raise ContractViolation(
                message=f"PostgreSQL connection failed: {e}",
                clause_type="requires",
                context={"url": url, "error": str(e)},
            )

    @staticmethod
    def query(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """查询所有行，返回 List[Dict]

        Args:
            handle: 连接句柄
            sql: SQL 查询语句 (使用 $1, $2... 占位符)
            params: 参数列表

        Returns:
            每行一个字典的列表
        """
        if not _PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 is not installed")

        if not _is_valid_handle(handle):
            raise ContractViolation(
                message="Invalid or disconnected database handle",
                clause_type="requires",
                context={"handle": handle},
            )

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is None:
            raise ContractViolation(
                message=f"Connection {conn_id} not found in registry",
                clause_type="requires",
                context={"conn_id": conn_id},
            )

        try:
            # 适配占位符: 将 ? 转换为 $1, $2...
            adapted_sql, adapted_params = adapt_sql_params(sql, params or [], "postgres")
            converted_params = [python_to_sql(p) for p in adapted_params]

            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(adapted_sql, converted_params)
            rows = cursor.fetchall()

            result = []
            for row in rows:
                row_dict = {}
                for key, val in row.items():
                    row_dict[key] = sql_to_python(val)
                result.append(row_dict)
            return result

        except Exception as e:
            raise ContractViolation(
                message=f"PostgreSQL query failed: {e}",
                clause_type="requires",
                context={"sql": sql, "params": params, "error": str(e)},
            )

    @staticmethod
    def query_one(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
        """查询单行，返回 Optional[Dict]"""
        results = NexaPostgres.query(handle, sql, params)
        if results:
            return results[0]
        return None

    @staticmethod
    def execute(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> int:
        """执行写操作，返回受影响行数"""
        if not _PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 is not installed")

        if not _is_valid_handle(handle):
            raise ContractViolation(
                message="Invalid or disconnected database handle",
                clause_type="requires",
                context={"handle": handle},
            )

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is None:
            raise ContractViolation(
                message=f"Connection {conn_id} not found in registry",
                clause_type="requires",
                context={"conn_id": conn_id},
            )

        try:
            adapted_sql, adapted_params = adapt_sql_params(sql, params or [], "postgres")
            converted_params = [python_to_sql(p) for p in adapted_params]

            cursor = conn.cursor()
            cursor.execute(adapted_sql, converted_params)
            conn.commit()
            return cursor.rowcount

        except Exception as e:
            conn.rollback()
            raise ContractViolation(
                message=f"PostgreSQL execute failed: {e}",
                clause_type="requires",
                context={"sql": sql, "params": params, "error": str(e)},
            )

    @staticmethod
    def close(handle: Dict[str, Any]) -> bool:
        """关闭连接，从注册表移除"""
        if not isinstance(handle, dict):
            return False

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            _unregister_connection(conn_id)

        handle["connected"] = False
        return True

    @staticmethod
    def begin(handle: Dict[str, Any]) -> Dict[str, Any]:
        """开始事务"""
        if not _PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 is not installed")

        if not _is_valid_handle(handle):
            raise ContractViolation(
                message="Invalid or disconnected database handle",
                clause_type="requires",
                context={"handle": handle},
            )

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is None:
            raise ContractViolation(
                message=f"Connection {conn_id} not found in registry",
                clause_type="requires",
                context={"conn_id": conn_id},
            )

        # psycopg2 默认在 autocommit=False 时自动开始事务
        # 无需显式 BEGIN，但我们可以确认连接状态
        return handle

    @staticmethod
    def commit(handle: Dict[str, Any]) -> bool:
        """提交事务"""
        if not _PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 is not installed")

        if not _is_valid_handle(handle):
            raise ContractViolation(
                message="Invalid or disconnected database handle",
                clause_type="requires",
                context={"handle": handle},
            )

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is None:
            raise ContractViolation(
                message=f"Connection {conn_id} not found in registry",
                clause_type="requires",
                context={"conn_id": conn_id},
            )

        try:
            conn.commit()
            return True
        except Exception as e:
            raise ContractViolation(
                message=f"PostgreSQL commit failed: {e}",
                clause_type="requires",
                context={"error": str(e)},
            )

    @staticmethod
    def rollback(handle: Dict[str, Any]) -> bool:
        """回滚事务"""
        if not _PSYCOPG2_AVAILABLE:
            raise ImportError("psycopg2 is not installed")

        if not _is_valid_handle(handle):
            raise ContractViolation(
                message="Invalid or disconnected database handle",
                clause_type="requires",
                context={"handle": handle},
            )

        conn_id = _get_conn_id_from_handle(handle)
        conn = _get_connection(conn_id)
        if conn is None:
            raise ContractViolation(
                message=f"Connection {conn_id} not found in registry",
                clause_type="requires",
                context={"conn_id": conn_id},
            )

        try:
            conn.rollback()
            return True
        except Exception as e:
            raise ContractViolation(
                message=f"PostgreSQL rollback failed: {e}",
                clause_type="requires",
                context={"error": str(e)},
            )


# ==================== NexaDatabase 统一接口 ====================

class NexaDatabase:
    """统一数据库接口 — 自动检测连接类型并路由到 SQLite 或 PostgreSQL

    所有静态方法接受连接句柄，根据 db_type 字段自动选择后端实现。
    """

    @staticmethod
    def connect(connection_string: str) -> Dict[str, Any]:
        """根据连接字符串自动判断数据库类型并连接

        Args:
            connection_string: 连接字符串
            - "sqlite://:memory:" → SQLite 内存数据库
            - "sqlite://path/to/db" → SQLite 文件数据库
            - ":memory:" → SQLite 内存数据库 (简写)
            - "postgres://..." → PostgreSQL 数据库
            - "postgresql://..." → PostgreSQL 数据库

        Returns:
            连接句柄字典
        """
        if connection_string.startswith("postgres://") or connection_string.startswith("postgresql://"):
            return NexaPostgres.connect(connection_string)
        else:
            # 默认 SQLite
            return NexaSQLite.connect(connection_string)

    @staticmethod
    def query(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """查询所有行 — 自动检测连接类型"""
        db_type = _get_db_type_from_handle(handle)
        if db_type == "postgres":
            return NexaPostgres.query(handle, sql, params)
        return NexaSQLite.query(handle, sql, params)

    @staticmethod
    def query_one(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
        """查询单行 — 自动检测连接类型"""
        db_type = _get_db_type_from_handle(handle)
        if db_type == "postgres":
            return NexaPostgres.query_one(handle, sql, params)
        return NexaSQLite.query_one(handle, sql, params)

    @staticmethod
    def execute(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> int:
        """执行写操作 — 自动检测连接类型"""
        db_type = _get_db_type_from_handle(handle)
        if db_type == "postgres":
            return NexaPostgres.execute(handle, sql, params)
        return NexaSQLite.execute(handle, sql, params)

    @staticmethod
    def close(handle: Dict[str, Any]) -> bool:
        """关闭连接 — 自动检测连接类型"""
        db_type = _get_db_type_from_handle(handle)
        if db_type == "postgres":
            return NexaPostgres.close(handle)
        return NexaSQLite.close(handle)

    @staticmethod
    def begin(handle: Dict[str, Any]) -> Dict[str, Any]:
        """开始事务 — 自动检测连接类型"""
        db_type = _get_db_type_from_handle(handle)
        if db_type == "postgres":
            return NexaPostgres.begin(handle)
        return NexaSQLite.begin(handle)

    @staticmethod
    def commit(handle: Dict[str, Any]) -> bool:
        """提交事务 — 自动检测连接类型"""
        db_type = _get_db_type_from_handle(handle)
        if db_type == "postgres":
            return NexaPostgres.commit(handle)
        return NexaSQLite.commit(handle)

    @staticmethod
    def rollback(handle: Dict[str, Any]) -> bool:
        """回滚事务 — 自动检测连接类型"""
        db_type = _get_db_type_from_handle(handle)
        if db_type == "postgres":
            return NexaPostgres.rollback(handle)
        return NexaSQLite.rollback(handle)


# ==================== 统一接口函数 (便捷入口) ====================

def query(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """查询所有行 — 统一接口"""
    return NexaDatabase.query(handle, sql, params)


def query_one(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
    """查询单行 — 统一接口"""
    return NexaDatabase.query_one(handle, sql, params)


def execute(handle: Dict[str, Any], sql: str, params: Optional[List[Any]] = None) -> int:
    """执行写操作 — 统一接口"""
    return NexaDatabase.execute(handle, sql, params)


def close(handle: Dict[str, Any]) -> bool:
    """关闭连接 — 统一接口"""
    return NexaDatabase.close(handle)


def begin(handle: Dict[str, Any]) -> Dict[str, Any]:
    """开始事务 — 统一接口"""
    return NexaDatabase.begin(handle)


def commit(handle: Dict[str, Any]) -> bool:
    """提交事务 — 统一接口"""
    return NexaDatabase.commit(handle)


def rollback(handle: Dict[str, Any]) -> bool:
    """回滚事务 — 统一接口"""
    return NexaDatabase.rollback(handle)


# ==================== Agent 记忆接口 ====================

# Agent 记忆表名
_AGENT_MEMORY_TABLE = "_nexa_agent_memory"


def _ensure_memory_table(handle: Dict[str, Any]) -> None:
    """确保 Agent 记忆表存在"""
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {_AGENT_MEMORY_TABLE} (
        agent_name TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        created_at REAL DEFAULT (strftime('%s', 'now')),
        updated_at REAL DEFAULT (strftime('%s', 'now')),
        PRIMARY KEY (agent_name, key)
    )
    """
    NexaDatabase.execute(handle, create_sql, [])


def agent_memory_query(handle: Dict[str, Any], agent_name: str, key: str) -> Optional[str]:
    """查询 Agent 长期记忆

    Args:
        handle: 数据库连接句柄
        agent_name: Agent 名称
        key: 记忆键名

    Returns:
        记忆值 (字符串)，如果不存在返回 None
    """
    _ensure_memory_table(handle)

    sql = f"SELECT value FROM {_AGENT_MEMORY_TABLE} WHERE agent_name = ? AND key = ?"
    result = NexaDatabase.query_one(handle, sql, [agent_name, key])
    if result:
        return result.get("value")
    return None


def agent_memory_store(handle: Dict[str, Any], agent_name: str, key: str, value: str) -> bool:
    """存储 Agent 长期记忆

    Args:
        handle: 数据库连接句柄
        agent_name: Agent 名称
        key: 记忆键名
        value: 记忆值 (字符串)

    Returns:
        True 如果存储成功
    """
    _ensure_memory_table(handle)

    # 使用 UPSERT (INSERT OR REPLACE) 语义
    sql = f"""
    INSERT OR REPLACE INTO {_AGENT_MEMORY_TABLE} (agent_name, key, value, updated_at)
    VALUES (?, ?, ?, strftime('%s', 'now'))
    """
    try:
        NexaDatabase.execute(handle, sql, [agent_name, key, value])
        return True
    except Exception:
        return False


def agent_memory_delete(handle: Dict[str, Any], agent_name: str, key: str) -> bool:
    """删除 Agent 长期记忆

    Args:
        handle: 数据库连接句柄
        agent_name: Agent 名称
        key: 记忆键名

    Returns:
        True 如果删除成功
    """
    _ensure_memory_table(handle)

    sql = f"DELETE FROM {_AGENT_MEMORY_TABLE} WHERE agent_name = ? AND key = ?"
    try:
        NexaDatabase.execute(handle, sql, [agent_name, key])
        return True
    except Exception:
        return False


def agent_memory_list(handle: Dict[str, Any], agent_name: str) -> List[Dict[str, Any]]:
    """列出 Agent 所有长期记忆

    Args:
        handle: 数据库连接句柄
        agent_name: Agent 名称

    Returns:
        记忆列表，每项包含 key, value, created_at, updated_at
    """
    _ensure_memory_table(handle)

    sql = f"SELECT key, value, created_at, updated_at FROM {_AGENT_MEMORY_TABLE} WHERE agent_name = ?"
    return NexaDatabase.query(handle, sql, [agent_name])


# ==================== 契约违反映射 ====================

def contract_violation_to_http_status(violation: ContractViolation) -> int:
    """将 ContractViolation 映射为 HTTP 状态码

    规则:
    - 连接失败 → 500 Internal Server Error
    - 查询参数错误 → 400 Bad Request
    - 其他 → 500 Internal Server Error
    """
    msg = str(violation)
    if "connection failed" in msg.lower():
        return 500
    if "query failed" in msg.lower() or "execute failed" in msg.lower():
        # 区分参数错误和其他错误
        if "syntax" in msg.lower() or "parameter" in msg.lower() or "params" in msg.lower():
            return 400
        return 500
    return 500


# ==================== WAL 模式验证 ====================

def verify_wal_mode(handle: Dict[str, Any]) -> bool:
    """验证 SQLite 连接是否启用 WAL 模式

    Args:
        handle: SQLite 连接句柄

    Returns:
        True 如果 WAL 模式已启用
    """
    if _get_db_type_from_handle(handle) != "sqlite":
        return False  # PostgreSQL 不需要 WAL 验证

    result = NexaSQLite.query_one(handle, "PRAGMA journal_mode", [])
    if result:
        mode = list(result.values())[0]
        return mode == "wal"
    return False


def verify_foreign_keys(handle: Dict[str, Any]) -> bool:
    """验证 SQLite 连接是否启用外键约束

    Args:
        handle: SQLite 连接句柄

    Returns:
        True 如果外键约束已启用
    """
    if _get_db_type_from_handle(handle) != "sqlite":
        return False  # PostgreSQL 默认启用外键

    result = NexaSQLite.query_one(handle, "PRAGMA foreign_keys", [])
    if result:
        val = list(result.values())[0]
        return val == 1
    return False


# ==================== 错误处理 ====================

class DatabaseError(Exception):
    """数据库操作错误基类

    Attributes:
        db_type: 'sqlite' 或 'postgres'
        operation: 操作类型 ('connect', 'query', 'execute', etc.)
        original_error: 原始异常
        http_status: 推荐的 HTTP 状态码
    """

    def __init__(self, message: str, db_type: str = "sqlite",
                 operation: str = "", original_error: Optional[Exception] = None,
                 http_status: int = 500):
        super().__init__(message)
        self.db_type = db_type
        self.operation = operation
        self.original_error = original_error
        self.http_status = http_status

    def __repr__(self):
        return f"DatabaseError({self.db_type}:{self.operation}, status={self.http_status}, message={self.args[0]})"

    def to_contract_violation(self) -> ContractViolation:
        """转换为 ContractViolation"""
        return ContractViolation(
            message=str(self),
            clause_type="requires",
            context={
                "db_type": self.db_type,
                "operation": self.operation,
                "http_status": self.http_status,
                "original_error": str(self.original_error) if self.original_error else None,
            },
        )


# ==================== 导出 ====================

__all__ = [
    # Core classes
    "NexaDatabase", "NexaSQLite", "NexaPostgres",
    # Unified interface functions
    "query", "query_one", "execute", "close", "begin", "commit", "rollback",
    # Type conversion
    "python_to_sql", "sql_to_python",
    # Parameter adaptation
    "adapt_sql_params",
    # Agent memory interface
    "agent_memory_query", "agent_memory_store", "agent_memory_delete", "agent_memory_list",
    # Contract violation mapping
    "contract_violation_to_http_status",
    # Connection registry
    "get_active_connections",
    # WAL / FK verification
    "verify_wal_mode", "verify_foreign_keys",
    # Error handling
    "DatabaseError",
    # Handle utilities
    "_make_handle", "_is_valid_handle", "_get_db_type_from_handle", "_get_conn_id_from_handle",
    # Constants
    "_PSYCOPG2_AVAILABLE",
]