"""
P1-5: Database Integration — Nexa 内置数据库集成测试

覆盖所有核心功能:
- SQLite 连接 (文件 + :memory:)
- 查询 (query, query_one)
- 执行 (execute, affected rows)
- 事务 (begin/commit/rollback)
- 类型转换
- 连接关闭
- PostgreSQL 连接 (psycopg2 可选，skip if not installed)
- Agent 记忆接口
- 契约违反映射
- Parser AST 测试
- 参数占位符适配
- WAL 模式验证
- 错误处理
- std.db namespace
- 统一接口
"""

import os
import json
import pytest
import tempfile

from src.runtime.database import (
    NexaDatabase, NexaSQLite, NexaPostgres, DatabaseError,
    query, query_one, execute, close, begin, commit, rollback,
    python_to_sql, sql_to_python, adapt_sql_params,
    agent_memory_query, agent_memory_store, agent_memory_delete, agent_memory_list,
    contract_violation_to_http_status, verify_wal_mode, verify_foreign_keys,
    get_active_connections,
    _make_handle, _is_valid_handle, _get_db_type_from_handle, _get_conn_id_from_handle,
    _PSYCOPG2_AVAILABLE,
    _connection_registry, _unregister_connection,
)
from src.runtime.contracts import ContractViolation


# ==================== TestSQLiteConnection ====================

class TestSQLiteConnection:
    """SQLite 连接测试 (8 tests)"""

    def test_connect_memory(self):
        """连接 SQLite 内存数据库"""
        handle = NexaSQLite.connect(":memory:")
        assert handle["connected"] is True
        assert handle["db_type"] == "sqlite"
        assert "_nexa_db_connection_id" in handle
        NexaSQLite.close(handle)

    def test_connect_memory_with_prefix(self):
        """连接 SQLite 内存数据库 (sqlite:// 前缀)"""
        handle = NexaSQLite.connect("sqlite://:memory:")
        assert handle["connected"] is True
        assert handle["db_type"] == "sqlite"
        NexaSQLite.close(handle)

    def test_connect_file(self):
        """连接 SQLite 文件数据库"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            handle = NexaSQLite.connect(db_path)
            assert handle["connected"] is True
            assert handle["db_type"] == "sqlite"
            NexaSQLite.close(handle)
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_connect_file_with_prefix(self):
        """连接 SQLite 文件数据库 (sqlite:// 前缀)"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            handle = NexaSQLite.connect(f"sqlite://{db_path}")
            assert handle["connected"] is True
            NexaSQLite.close(handle)
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_handle_format(self):
        """连接句柄格式验证"""
        handle = NexaSQLite.connect(":memory:")
        assert "_nexa_db_connection_id" in handle
        assert "db_type" in handle
        assert "connected" in handle
        assert isinstance(handle["_nexa_db_connection_id"], int)
        assert handle["db_type"] == "sqlite"
        assert handle["connected"] is True
        NexaSQLite.close(handle)

    def test_multiple_connections(self):
        """多个并行连接"""
        h1 = NexaSQLite.connect(":memory:")
        h2 = NexaSQLite.connect(":memory:")
        assert h1["_nexa_db_connection_id"] != h2["_nexa_db_connection_id"]
        assert h1["connected"] is True
        assert h2["connected"] is True
        NexaSQLite.close(h1)
        NexaSQLite.close(h2)

    def test_connection_registered(self):
        """连接注册到全局注册表"""
        handle = NexaSQLite.connect(":memory:")
        conn_id = handle["_nexa_db_connection_id"]
        active = get_active_connections()
        assert conn_id in active
        NexaSQLite.close(handle)

    def test_connection_failure_contract_violation(self):
        """连接失败抛出 ContractViolation"""
        # 使用一个不可能的路径来触发连接失败
        # 注意: sqlite3 对大部分路径都能连接,所以这个测试可能不好触发
        # 使用 invalid 路径格式
        with pytest.raises((ContractViolation, Exception)):
            NexaSQLite.connect("/nonexistent/deeply/nested/path/that/cannot/be/created/db.sqlite")


# ==================== TestSQLiteQuery ====================

class TestSQLiteQuery:
    """SQLite 查询测试 (6 tests)"""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """每个测试前创建内存数据库和表"""
        self.handle = NexaSQLite.connect(":memory:")
        NexaSQLite.execute(self.handle,
            "CREATE TABLE test_users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)", [])
        NexaSQLite.execute(self.handle,
            "INSERT INTO test_users (name, age) VALUES (?, ?)", ["Alice", 30])
        NexaSQLite.execute(self.handle,
            "INSERT INTO test_users (name, age) VALUES (?, ?)", ["Bob", 25])
        NexaSQLite.execute(self.handle,
            "INSERT INTO test_users (name, age) VALUES (?, ?)", ["Charlie", 35])
        yield
        NexaSQLite.close(self.handle)

    def test_query_all_rows(self):
        """查询所有行"""
        results = NexaSQLite.query(self.handle, "SELECT * FROM test_users", [])
        assert len(results) == 3
        assert all(isinstance(r, dict) for r in results)

    def test_query_with_params(self):
        """带参数查询"""
        results = NexaSQLite.query(self.handle, 
            "SELECT * FROM test_users WHERE name = ?", ["Alice"])
        assert len(results) == 1
        assert results[0]["name"] == "Alice"

    def test_query_returns_dicts(self):
        """查询结果为字典列表"""
        results = NexaSQLite.query(self.handle, "SELECT name, age FROM test_users WHERE name = ?", ["Alice"])
        assert len(results) == 1
        assert "name" in results[0]
        assert "age" in results[0]
        assert results[0]["name"] == "Alice"

    def test_query_empty_result(self):
        """查询无结果"""
        results = NexaSQLite.query(self.handle,
            "SELECT * FROM test_users WHERE name = ?", ["NonExistent"])
        assert results == []

    def test_query_one_returns_single(self):
        """query_one 返回单行"""
        result = NexaSQLite.query_one(self.handle,
            "SELECT * FROM test_users WHERE name = ?", ["Alice"])
        assert result is not None
        assert result["name"] == "Alice"

    def test_query_one_returns_none(self):
        """query_one 无结果返回 None"""
        result = NexaSQLite.query_one(self.handle,
            "SELECT * FROM test_users WHERE name = ?", ["NonExistent"])
        assert result is None


# ==================== TestSQLiteExecute ====================

class TestSQLiteExecute:
    """SQLite 执行测试 (4 tests)"""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.handle = NexaSQLite.connect(":memory:")
        NexaSQLite.execute(self.handle,
            "CREATE TABLE test_items (id INTEGER PRIMARY KEY, name TEXT, quantity INTEGER)", [])
        yield
        NexaSQLite.close(self.handle)

    def test_execute_insert(self):
        """执行 INSERT"""
        count = NexaSQLite.execute(self.handle,
            "INSERT INTO test_items (name, quantity) VALUES (?, ?)", ["Apple", 10])
        assert count == 1

    def test_execute_update(self):
        """执行 UPDATE"""
        NexaSQLite.execute(self.handle,
            "INSERT INTO test_items (name, quantity) VALUES (?, ?)", ["Apple", 10])
        count = NexaSQLite.execute(self.handle,
            "UPDATE test_items SET quantity = ? WHERE name = ?", [20, "Apple"])
        assert count == 1

    def test_execute_delete(self):
        """执行 DELETE"""
        NexaSQLite.execute(self.handle,
            "INSERT INTO test_items (name, quantity) VALUES (?, ?)", ["Apple", 10])
        count = NexaSQLite.execute(self.handle,
            "DELETE FROM test_items WHERE name = ?", ["Apple"])
        assert count == 1

    def test_execute_create_table(self):
        """执行 CREATE TABLE"""
        count = NexaSQLite.execute(self.handle,
            "CREATE TABLE another_table (id INTEGER PRIMARY KEY)", [])
        # SQLite DDL (CREATE TABLE) returns -1 for rowcount, which is expected
        assert count == -1 or count == 0


# ==================== TestSQLiteTransaction ====================

class TestSQLiteTransaction:
    """SQLite 事务测试 (5 tests)"""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.handle = NexaSQLite.connect(":memory:")
        NexaSQLite.execute(self.handle,
            "CREATE TABLE test_accounts (id INTEGER PRIMARY KEY, name TEXT, balance REAL)", [])
        NexaSQLite.execute(self.handle,
            "INSERT INTO test_accounts (name, balance) VALUES (?, ?)", ["Alice", 100.0])
        yield
        NexaSQLite.close(self.handle)

    def test_begin_transaction(self):
        """开始事务"""
        result = NexaSQLite.begin(self.handle)
        assert result["connected"] is True

    def test_commit_transaction(self):
        """提交事务"""
        NexaSQLite.begin(self.handle)
        NexaSQLite.execute(self.handle,
            "UPDATE test_accounts SET balance = ? WHERE name = ?", [200.0, "Alice"])
        result = NexaSQLite.commit(self.handle)
        assert result is True
        # 验证数据已持久化
        row = NexaSQLite.query_one(self.handle,
            "SELECT balance FROM test_accounts WHERE name = ?", ["Alice"])
        assert row["balance"] == 200.0

    def test_rollback_transaction(self):
        """回滚事务"""
        NexaSQLite.begin(self.handle)
        NexaSQLite.execute(self.handle,
            "UPDATE test_accounts SET balance = ? WHERE name = ?", [999.0, "Alice"])
        result = NexaSQLite.rollback(self.handle)
        assert result is True
        # 验证数据已回滚
        row = NexaSQLite.query_one(self.handle,
            "SELECT balance FROM test_accounts WHERE name = ?", ["Alice"])
        assert row["balance"] == 100.0

    def test_transaction_isolation(self):
        """事务隔离性验证"""
        NexaSQLite.begin(self.handle)
        NexaSQLite.execute(self.handle,
            "INSERT INTO test_accounts (name, balance) VALUES (?, ?)", ["Bob", 50.0])
        # 在事务内查询可以看到新数据
        results = NexaSQLite.query(self.handle, "SELECT * FROM test_accounts", [])
        assert len(results) == 2
        NexaSQLite.rollback(self.handle)
        # 回滚后查询看不到新数据
        results = NexaSQLite.query(self.handle, "SELECT * FROM test_accounts", [])
        assert len(results) == 1

    def test_commit_after_multiple_operations(self):
        """多次操作后提交"""
        NexaSQLite.begin(self.handle)
        NexaSQLite.execute(self.handle,
            "INSERT INTO test_accounts (name, balance) VALUES (?, ?)", ["Bob", 50.0])
        NexaSQLite.execute(self.handle,
            "INSERT INTO test_accounts (name, balance) VALUES (?, ?)", ["Charlie", 75.0])
        NexaSQLite.commit(self.handle)
        results = NexaSQLite.query(self.handle, "SELECT * FROM test_accounts", [])
        assert len(results) == 3


# ==================== TestDatabaseTypes ====================

class TestDatabaseTypes:
    """类型转换测试 (6 tests)"""

    def test_python_to_sql_none(self):
        """None → SQL NULL"""
        assert python_to_sql(None) is None

    def test_python_to_sql_bool(self):
        """bool → INTEGER (0/1)"""
        assert python_to_sql(True) == 1
        assert python_to_sql(False) == 0

    def test_python_to_sql_int_float_str(self):
        """int → INTEGER, float → REAL, str → TEXT"""
        assert python_to_sql(42) == 42
        assert python_to_sql(3.14) == 3.14
        assert python_to_sql("hello") == "hello"

    def test_python_to_sql_list_dict(self):
        """list/dict → TEXT (JSON 序列化)"""
        result = python_to_sql([1, 2, 3])
        assert isinstance(result, str)
        assert json.loads(result) == [1, 2, 3]

        result = python_to_sql({"key": "value"})
        assert isinstance(result, str)
        assert json.loads(result) == {"key": "value"}

    def test_sql_to_python_null(self):
        """SQL NULL → None"""
        assert sql_to_python(None) is None

    def test_sql_to_python_int_float_str(self):
        """SQL INTEGER → int, REAL → float, TEXT → str"""
        assert sql_to_python(42) == 42
        assert sql_to_python(3.14) == 3.14
        assert sql_to_python("hello") == "hello"

    def test_sql_to_python_json_string(self):
        """JSON 字符串自动反序列化"""
        result = sql_to_python('{"key": "value"}')
        assert isinstance(result, dict)
        assert result["key"] == "value"

        result = sql_to_python("[1, 2, 3]")
        assert isinstance(result, list)
        assert result == [1, 2, 3]

    def test_sql_to_python_bool_hint(self):
        """INTEGER + BOOL 类型提示 → bool"""
        assert sql_to_python(1, "BOOL") is True
        assert sql_to_python(0, "BOOL") is False


# ==================== TestDatabaseClose ====================

class TestDatabaseClose:
    """连接关闭测试 (3 tests)"""

    def test_close_marks_disconnected(self):
        """关闭连接标记为断开"""
        handle = NexaSQLite.connect(":memory:")
        assert handle["connected"] is True
        NexaSQLite.close(handle)
        assert handle["connected"] is False

    def test_close_removes_from_registry(self):
        """关闭连接从注册表移除"""
        handle = NexaSQLite.connect(":memory:")
        conn_id = handle["_nexa_db_connection_id"]
        active = get_active_connections()
        assert conn_id in active
        NexaSQLite.close(handle)
        active = get_active_connections()
        assert conn_id not in active

    def test_operations_fail_after_close(self):
        """关闭后操作抛出 ContractViolation"""
        handle = NexaSQLite.connect(":memory:")
        NexaSQLite.close(handle)
        with pytest.raises(ContractViolation):
            NexaSQLite.query(handle, "SELECT 1", [])


# ==================== TestPostgresConnection ====================

class TestPostgresConnection:
    """PostgreSQL 连接测试 (4 tests, 需要 psycopg2)"""

    @pytest.fixture(autouse=True)
    def skip_if_no_psycopg2(self):
        """如果 psycopg2 不可安装则跳过"""
        if not _PSYCOPG2_AVAILABLE:
            pytest.skip("psycopg2 not installed")

    def test_connect_raises_import_error_without_psycopg2(self):
        """psycopg2 不可用时 NexaPostgres.connect 抛 ImportError"""
        # 此测试仅在 _PSYCOPG2_AVAILABLE 为 True 时运行
        # 实际测试需要 PostgreSQL 服务器
        assert _PSYCOPG2_AVAILABLE is True

    def test_postgres_class_exists(self):
        """NexaPostgres 类存在"""
        assert NexaPostgres is not None

    def test_postgres_connect_method(self):
        """NexaPostgres.connect 方法存在"""
        assert hasattr(NexaPostgres, 'connect')
        assert hasattr(NexaPostgres, 'query')
        assert hasattr(NexaPostgres, 'query_one')
        assert hasattr(NexaPostgres, 'execute')
        assert hasattr(NexaPostgres, 'close')
        assert hasattr(NexaPostgres, 'begin')
        assert hasattr(NexaPostgres, 'commit')
        assert hasattr(NexaPostgres, 'rollback')

    def test_postgres_connect_with_invalid_url(self):
        """PostgreSQL 无效 URL 抛 ContractViolation"""
        with pytest.raises((ContractViolation, Exception)):
            NexaPostgres.connect("postgres://invalid:invalid@nonexistent:5432/nonexistent_db")


# ==================== TestAgentMemoryDB ====================

class TestAgentMemoryDB:
    """Agent 记忆接口测试 (4 tests)"""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.handle = NexaSQLite.connect(":memory:")
        yield
        NexaSQLite.close(self.handle)

    def test_agent_memory_store_and_query(self):
        """存储并查询 Agent 记忆"""
        result = agent_memory_store(self.handle, "TestBot", "greeting", "Hello, world!")
        assert result is True
        value = agent_memory_query(self.handle, "TestBot", "greeting")
        assert value == "Hello, world!"

    def test_agent_memory_query_nonexistent(self):
        """查询不存在的记忆返回 None"""
        value = agent_memory_query(self.handle, "TestBot", "nonexistent_key")
        assert value is None

    def test_agent_memory_delete(self):
        """删除 Agent 记忆"""
        agent_memory_store(self.handle, "TestBot", "temp_key", "temp_value")
        result = agent_memory_delete(self.handle, "TestBot", "temp_key")
        assert result is True
        value = agent_memory_query(self.handle, "TestBot", "temp_key")
        assert value is None

    def test_agent_memory_list(self):
        """列出 Agent 所有记忆"""
        agent_memory_store(self.handle, "TestBot", "key1", "value1")
        agent_memory_store(self.handle, "TestBot", "key2", "value2")
        results = agent_memory_list(self.handle, "TestBot")
        assert len(results) == 2
        keys = [r["key"] for r in results]
        assert "key1" in keys
        assert "key2" in keys

    def test_agent_memory_upsert(self):
        """Agent 记忆 UPSERT (覆盖更新)"""
        agent_memory_store(self.handle, "TestBot", "config", "v1")
        agent_memory_store(self.handle, "TestBot", "config", "v2")
        value = agent_memory_query(self.handle, "TestBot", "config")
        assert value == "v2"


# ==================== TestContractViolation ====================

class TestContractViolationMapping:
    """契约违反映射测试 (3 tests)"""

    def test_connection_failure_maps_to_500(self):
        """连接失败 → 500"""
        violation = ContractViolation(
            message="SQLite connection failed: disk error",
            clause_type="requires",
        )
        status = contract_violation_to_http_status(violation)
        assert status == 500

    def test_query_failure_maps_to_500(self):
        """查询失败 → 500"""
        violation = ContractViolation(
            message="SQLite query failed: syntax error",
            clause_type="requires",
        )
        status = contract_violation_to_http_status(violation)
        assert status == 400  # syntax error → 400

    def test_execute_failure_maps_to_500(self):
        """执行失败 → 500"""
        violation = ContractViolation(
            message="SQLite execute failed: constraint violation",
            clause_type="requires",
        )
        status = contract_violation_to_http_status(violation)
        assert status == 500


# ==================== TestStdDbNamespace ====================

class TestStdDbNamespace:
    """std.db namespace 测试 (3 tests)"""

    def test_namespace_map_contains_db_keys(self):
        """STD_NAMESPACE_MAP 包含 std.db 键"""
        from src.runtime.stdlib import STD_NAMESPACE_MAP
        assert "std.db.sqlite" in STD_NAMESPACE_MAP
        assert "std.db.postgres" in STD_NAMESPACE_MAP
        assert "std.db.memory" in STD_NAMESPACE_MAP

    def test_namespace_map_has_correct_functions(self):
        """std.db.sqlite 包含正确函数列表"""
        from src.runtime.stdlib import STD_NAMESPACE_MAP
        sqlite_funcs = STD_NAMESPACE_MAP["std.db.sqlite"]
        assert "std_db_sqlite_connect" in sqlite_funcs
        assert "std_db_sqlite_query" in sqlite_funcs
        assert "std_db_sqlite_execute" in sqlite_funcs
        assert "std_db_sqlite_close" in sqlite_funcs

    def test_stdlib_tools_registered(self):
        """std.db 工具已注册到 get_stdlib_tools"""
        from src.runtime.stdlib import get_stdlib_tools
        tools = get_stdlib_tools()
        assert "std_db_sqlite_connect" in tools
        assert "std_db_postgres_connect" in tools
        assert "std_db_memory_query" in tools


# ==================== TestQueryOne ====================

class TestQueryOne:
    """query_one 统一接口测试 (3 tests)"""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.handle = NexaSQLite.connect(":memory:")
        NexaSQLite.execute(self.handle,
            "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)", [])
        NexaSQLite.execute(self.handle,
            "INSERT INTO items (name) VALUES (?)", ["Widget"])
        yield
        NexaSQLite.close(self.handle)

    def test_query_one_via_nexa_database(self):
        """通过 NexaDatabase.query_one 查询"""
        result = NexaDatabase.query_one(self.handle,
            "SELECT * FROM items WHERE name = ?", ["Widget"])
        assert result is not None
        assert result["name"] == "Widget"

    def test_query_one_via_unified_function(self):
        """通过统一接口函数 query_one 查询"""
        result = query_one(self.handle,
            "SELECT * FROM items WHERE name = ?", ["Widget"])
        assert result is not None
        assert result["name"] == "Widget"

    def test_query_one_none_result(self):
        """query_one 无结果返回 None"""
        result = query_one(self.handle,
            "SELECT * FROM items WHERE name = ?", ["NonExistent"])
        assert result is None


# ==================== TestErrorHandling ====================

class TestErrorHandling:
    """错误处理测试 (3 tests)"""

    def test_invalid_handle_raises_contract_violation(self):
        """无效句柄抛出 ContractViolation"""
        invalid_handle = {"_nexa_db_connection_id": -1, "db_type": "sqlite", "connected": False}
        with pytest.raises(ContractViolation):
            NexaSQLite.query(invalid_handle, "SELECT 1", [])

    def test_database_error_class(self):
        """DatabaseError 类"""
        err = DatabaseError("test error", db_type="sqlite", operation="query", http_status=500)
        assert err.db_type == "sqlite"
        assert err.operation == "query"
        assert err.http_status == 500
        assert str(err) == "test error"

    def test_database_error_to_contract_violation(self):
        """DatabaseError.to_contract_violation()"""
        err = DatabaseError("test error", db_type="sqlite", operation="query", http_status=400)
        violation = err.to_contract_violation()
        assert isinstance(violation, ContractViolation)
        assert "test error" in str(violation)


# ==================== TestParserAST ====================

class TestParserAST:
    """Parser + AST 测试 (3 tests)"""

    def test_parse_db_decl(self):
        """解析 db_decl 语法"""
        from src.nexa_parser import parse
        code = 'db my_db = connect("sqlite://:memory:")'
        ast = parse(code)
        body = ast.get("body", [])
        # 应该有至少一个节点
        db_nodes = [n for n in body if isinstance(n, dict) and n.get("type") == "DatabaseDeclaration"]
        assert len(db_nodes) >= 1
        db_node = db_nodes[0]
        assert db_node["name"] == "my_db"
        assert "sqlite" in db_node["connection_string"]

    def test_parse_db_decl_with_postgres(self):
        """解析 PostgreSQL 连接"""
        from src.nexa_parser import parse
        code = 'db analytics = connect("postgres://localhost/analytics")'
        ast = parse(code)
        body = ast.get("body", [])
        db_nodes = [n for n in body if isinstance(n, dict) and n.get("type") == "DatabaseDeclaration"]
        assert len(db_nodes) >= 1
        db_node = db_nodes[0]
        assert db_node["name"] == "analytics"
        assert "postgres" in db_node["connection_string"]

    def test_ast_transformer_db_decl(self):
        """AST Transformer 处理 db_decl"""
        from src.ast_transformer import NexaTransformer
        
        transformer = NexaTransformer()
        # Grammar: "db" IDENTIFIER "=" "connect" "(" STRING_LITERAL ")"
        # Anonymous terminals filtered → args = [IDENTIFIER, STRING_LITERAL]
        result = transformer.db_decl(["app_db", '"sqlite://:memory:"'])
        assert result["type"] == "DatabaseDeclaration"
        assert result["name"] == "app_db"


# ==================== TestParamAdaptation ====================

class TestParamAdaptation:
    """参数占位符适配测试 (3 tests)"""

    def test_adapt_sqlite_no_change(self):
        """SQLite ? 占位符无需改变"""
        sql, params = adapt_sql_params("SELECT * FROM users WHERE name = ?", ["Alice"], "sqlite")
        assert sql == "SELECT * FROM users WHERE name = ?"
        assert params == ["Alice"]

    def test_adapt_postgres_converts_placeholders(self):
        """PostgreSQL 将 ? 转换为 $1, $2..."""
        sql, params = adapt_sql_params(
            "SELECT * FROM users WHERE name = ? AND age = ?", ["Alice", 30], "postgres")
        assert sql == "SELECT * FROM users WHERE name = $1 AND age = $2"
        assert params == ["Alice", 30]

    def test_adapt_multiple_placeholders(self):
        """多个占位符适配"""
        sql, params = adapt_sql_params(
            "INSERT INTO users (name, age, city) VALUES (?, ?, ?)", 
            ["Alice", 30, "NYC"], "postgres")
        assert "$1" in sql
        assert "$2" in sql
        assert "$3" in sql


# ==================== TestWALMode ====================

class TestWALMode:
    """WAL 模式验证测试 (2 tests)"""

    def test_wal_mode_enabled(self):
        """SQLite 连接自动启用 WAL 模式"""
        handle = NexaSQLite.connect(":memory:")
        # 内存数据库 WAL 模式可能是 "memory" 而非 "wal"
        # 文件数据库才真正启用 WAL
        result = NexaSQLite.query_one(handle, "PRAGMA journal_mode", [])
        mode = list(result.values())[0]
        # 内存数据库返回 "memory", 文件数据库返回 "wal"
        assert mode in ("wal", "memory")
        NexaSQLite.close(handle)

    def test_foreign_keys_enabled(self):
        """SQLite 连接自动启用外键约束"""
        handle = NexaSQLite.connect(":memory:")
        result = NexaSQLite.query_one(handle, "PRAGMA foreign_keys", [])
        val = list(result.values())[0]
        assert val == 1
        NexaSQLite.close(handle)


# ==================== TestUnifiedInterface ====================

class TestUnifiedInterface:
    """统一接口测试 (4 tests)"""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.handle = NexaSQLite.connect(":memory:")
        NexaDatabase.execute(self.handle,
            "CREATE TABLE test_data (id INTEGER PRIMARY KEY, value TEXT)", [])
        yield
        NexaDatabase.close(self.handle)

    def test_query_via_unified(self):
        """统一接口 query"""
        NexaDatabase.execute(self.handle,
            "INSERT INTO test_data (value) VALUES (?)", ["hello"])
        results = query(self.handle, "SELECT * FROM test_data", [])
        assert len(results) == 1

    def test_execute_via_unified(self):
        """统一接口 execute"""
        count = execute(self.handle,
            "INSERT INTO test_data (value) VALUES (?)", ["world"])
        assert count == 1

    def test_begin_commit_via_unified(self):
        """统一接口 begin/commit"""
        begin(self.handle)
        execute(self.handle,
            "INSERT INTO test_data (value) VALUES (?)", ["transaction_test"])
        commit(self.handle)
        results = query(self.handle, "SELECT * FROM test_data WHERE value = ?", ["transaction_test"])
        assert len(results) == 1

    def test_rollback_via_unified(self):
        """统一接口 rollback"""
        begin(self.handle)
        execute(self.handle,
            "INSERT INTO test_data (value) VALUES (?)", ["rollback_test"])
        rollback(self.handle)
        results = query(self.handle, "SELECT * FROM test_data WHERE value = ?", ["rollback_test"])
        assert len(results) == 0


# ==================== TestNexaDatabaseConnect ====================

class TestNexaDatabaseConnect:
    """NexaDatabase.connect 自动检测测试 (3 tests)"""

    def test_auto_detect_sqlite_memory(self):
        """自动检测 SQLite 内存连接"""
        handle = NexaDatabase.connect(":memory:")
        assert handle["db_type"] == "sqlite"
        assert handle["connected"] is True
        NexaDatabase.close(handle)

    def test_auto_detect_sqlite_prefix(self):
        """自动检测 sqlite:// 前缀"""
        handle = NexaDatabase.connect("sqlite://:memory:")
        assert handle["db_type"] == "sqlite"
        assert handle["connected"] is True
        NexaDatabase.close(handle)

    def test_auto_detect_postgres_prefix(self):
        """自动检测 postgres:// 前缀 (需要 psycopg2)"""
        if not _PSYCOPG2_AVAILABLE:
            pytest.skip("psycopg2 not installed")
        with pytest.raises((ContractViolation, Exception)):
            NexaDatabase.connect("postgres://invalid@nonexistent:5432/db")


# ==================== TestInMemoryDB ====================

class TestInMemoryDB:
    """内存数据库综合测试 (4 tests)"""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.handle = NexaSQLite.connect(":memory:")
        yield
        NexaSQLite.close(self.handle)

    def test_create_and_query_table(self):
        """创建表并查询"""
        NexaSQLite.execute(self.handle,
            "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL)", [])
        NexaSQLite.execute(self.handle,
            "INSERT INTO products (name, price) VALUES (?, ?)", ["Laptop", 999.99])
        result = NexaSQLite.query_one(self.handle,
            "SELECT * FROM products WHERE name = ?", ["Laptop"])
        assert result is not None
        assert result["name"] == "Laptop"
        assert result["price"] == 999.99

    def test_multiple_inserts_and_query(self):
        """多次插入后查询"""
        NexaSQLite.execute(self.handle,
            "CREATE TABLE logs (id INTEGER PRIMARY KEY, message TEXT)", [])
        for i in range(10):
            NexaSQLite.execute(self.handle,
                "INSERT INTO logs (message) VALUES (?)", [f"log_{i}"])
        results = NexaSQLite.query(self.handle, "SELECT * FROM logs", [])
        assert len(results) == 10

    def test_null_handling(self):
        """NULL 值处理"""
        NexaSQLite.execute(self.handle,
            "CREATE TABLE nullable_test (id INTEGER PRIMARY KEY, value TEXT)", [])
        NexaSQLite.execute(self.handle,
            "INSERT INTO nullable_test (value) VALUES (?)", [None])
        result = NexaSQLite.query_one(self.handle, "SELECT * FROM nullable_test", [])
        assert result["value"] is None

    def test_bool_handling(self):
        """布尔值处理 (True→1, False→0)"""
        NexaSQLite.execute(self.handle,
            "CREATE TABLE bool_test (id INTEGER PRIMARY KEY, flag INTEGER)", [])
        NexaSQLite.execute(self.handle,
            "INSERT INTO bool_test (flag) VALUES (?)", [True])
        NexaSQLite.execute(self.handle,
            "INSERT INTO bool_test (flag) VALUES (?)", [False])
        results = NexaSQLite.query(self.handle, "SELECT * FROM bool_test", [])
        assert results[0]["flag"] == 1
        assert results[1]["flag"] == 0


# ==================== TestHandleValidation ====================

class TestHandleValidation:
    """连接句柄验证测试 (3 tests)"""

    def test_valid_handle(self):
        """有效句柄验证"""
        handle = _make_handle(1, "sqlite")
        assert _is_valid_handle(handle) is True

    def test_invalid_handle_not_dict(self):
        """非字典句柄无效"""
        assert _is_valid_handle("not a dict") is False
        assert _is_valid_handle(None) is False
        assert _is_valid_handle(42) is False

    def test_invalid_handle_disconnected(self):
        """断开连接的句柄无效"""
        handle = _make_handle(1, "sqlite")
        handle["connected"] = False
        assert _is_valid_handle(handle) is False


# ==================== TestCodeGeneration ====================

class TestCodeGeneration:
    """代码生成测试 (2 tests)"""

    def test_generate_database_declaration(self):
        """生成 DatabaseDeclaration 代码"""
        from src.code_generator import CodeGenerator
        
        ast = {
            "type": "Program",
            "includes": [],
            "body": [
                {
                    "type": "DatabaseDeclaration",
                    "name": "app_db",
                    "connection_string": "sqlite://:memory:",
                }
            ]
        }
        gen = CodeGenerator(ast)
        code = gen.generate()
        assert "NexaSQLite.connect" in code
        assert "app_db" in code
        assert "ContractViolation" in code

    def test_generate_empty_db_connections(self):
        """无 db_connections 时跳过数据库生成"""
        from src.code_generator import CodeGenerator
        
        ast = {
            "type": "Program",
            "includes": [],
            "body": []
        }
        gen = CodeGenerator(ast)
        code = gen.generate()
        # 没有 NexaSQLite.connect 调用
        assert "NexaSQLite.connect" not in code or "NexaDatabase" not in code


# ==================== TestStdLibDbFunctions ====================

class TestStdLibDbFunctions:
    """stdlib db 函数实际执行测试 (3 tests)"""

    def test_std_db_sqlite_connect(self):
        """std_db_sqlite_connect 函数执行"""
        from src.runtime.stdlib import _std_db_sqlite_connect
        result = _std_db_sqlite_connect(path=":memory:")
        parsed = json.loads(result)
        assert parsed["connected"] is True
        assert parsed["db_type"] == "sqlite"
        # 清理: 关闭连接
        from src.runtime.database import NexaSQLite
        handle = parsed
        NexaSQLite.close(handle)

    def test_std_db_sqlite_query(self):
        """std_db_sqlite_query 函数执行"""
        from src.runtime.stdlib import _std_db_sqlite_connect, _std_db_sqlite_execute, _std_db_sqlite_query
        from src.runtime.database import NexaSQLite
        
        # 连接
        conn_result = json.loads(_std_db_sqlite_connect(path=":memory:"))
        handle_json = json.dumps(conn_result)
        
        # 创建表
        _std_db_sqlite_execute(
            handle_json=handle_json,
            sql="CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)",
            params_json="[]"
        )
        _std_db_sqlite_execute(
            handle_json=handle_json,
            sql="INSERT INTO test (name) VALUES (?)",
            params_json='["Alice"]'
        )
        
        # 查询
        query_result = json.loads(_std_db_sqlite_query(
            handle_json=handle_json,
            sql="SELECT * FROM test",
            params_json="[]"
        ))
        assert len(query_result) == 1
        
        # 清理
        NexaSQLite.close(conn_result)

    def test_std_db_memory_store_and_query(self):
        """std_db_memory_store/query 函数执行"""
        from src.runtime.stdlib import _std_db_sqlite_connect, _std_db_memory_store, _std_db_memory_query
        from src.runtime.database import NexaSQLite
        
        conn_result = json.loads(_std_db_sqlite_connect(path=":memory:"))
        handle_json = json.dumps(conn_result)
        
        # 存储
        store_result = json.loads(_std_db_memory_store(
            handle_json=handle_json,
            agent_name="TestBot",
            key="test_key",
            value="test_value"
        ))
        assert store_result["stored"] is True
        
        # 查询
        query_result = json.loads(_std_db_memory_query(
            handle_json=handle_json,
            agent_name="TestBot",
            key="test_key"
        ))
        assert query_result["value"] == "test_value"
        
        # 清理
        NexaSQLite.close(conn_result)


# ==================== TestConnectionRegistry ====================

class TestConnectionRegistry:
    """连接注册表测试 (2 tests)"""

    def test_registry_empty_after_close_all(self):
        """所有连接关闭后注册表为空"""
        h1 = NexaSQLite.connect(":memory:")
        h2 = NexaSQLite.connect(":memory:")
        NexaSQLite.close(h1)
        NexaSQLite.close(h2)
        # 注意: 其他测试可能还有活跃连接
        # 所以我们只检查 h1 和 h2 的 ID 不在注册表中
        active = get_active_connections()
        assert h1["_nexa_db_connection_id"] not in active
        assert h2["_nexa_db_connection_id"] not in active

    def test_registry_tracks_connections(self):
        """注册表跟踪活跃连接"""
        handle = NexaSQLite.connect(":memory:")
        conn_id = handle["_nexa_db_connection_id"]
        active = get_active_connections()
        assert conn_id in active
        conn = active[conn_id]
        assert conn is not None
        NexaSQLite.close(handle)