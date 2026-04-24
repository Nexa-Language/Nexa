# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
# 
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# Nexa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
# ========================================================================

'''
Nexa KV Store — Agent-Native 统一键值存储引擎

核心概念：
- KVHandle: KV 存储句柄，对标 NTNT KVStore Value
- NexaKVStore: 统一 KV 存储，SQLite backend
- 全局注册表: _kv_registry dict + _kv_id_counter 递增整数
- 线程安全: threading.Lock 保护注册表和 KV 操作
- SQLite 表名: _nexa_kv（不与 NTNT _kv 冲突，但结构兼容）

Nexa 特色（Agent-Native KV Fusion）：
- Layer 1: Generic KV — 与 NTNT 对齐的 15 通用键值操作
- Layer 2: Agent Memory KV — 语义搜索 + 上下文存储 + Agent 注入
- Layer 3: KV-Contract 联动 — 与 Nexa 契约系统集成

无新增外部依赖：sqlite3 + json + threading + time（全部 Python stdlib）
'''

import sqlite3
import json
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .contracts import ContractViolation


# ==================== 全局注册表 ====================

_kv_registry: Dict[int, 'NexaKVStore'] = {}
_kv_id_counter: int = 0
_registry_lock = threading.Lock()


def _next_kv_id() -> int:
    '''生成下一个 KV ID (线程安全)'''
    global _kv_id_counter
    with _registry_lock:
        _kv_id_counter += 1
        return _kv_id_counter


def _register_kv(kv_id: int, store: 'NexaKVStore') -> None:
    '''注册 KV 存储到全局注册表'''
    with _registry_lock:
        _kv_registry[kv_id] = store


def _unregister_kv(kv_id: int) -> None:
    '''从全局注册表移除 KV 存储'''
    with _registry_lock:
        _kv_registry.pop(kv_id, None)


def _get_kv_store(kv_id: int) -> Optional['NexaKVStore']:
    '''从全局注册表获取 KV 存储'''
    with _registry_lock:
        return _kv_registry.get(kv_id)


def get_active_kv_stores() -> Dict[int, 'NexaKVStore']:
    '''获取所有活跃 KV 存储的快照'''
    with _registry_lock:
        return dict(_kv_registry)


# ==================== 序列化/反序列化 ====================

def serialize_value(value: Any) -> Tuple[str, str]:
    '''将 Python 值序列化为 (serialized_data, type_hint)

    转换规则:
    - String -> (value, 'string')
    - Int -> (str(value), 'int')
    - Float -> (str(value), 'float')
    - Bool -> (str(value), 'bool')
    - Map/dict -> (json.dumps, 'map')
    - Array/list -> (json.dumps, 'array')
    - None/Unit -> 删除键（返回 None, 'none' 标记）
    '''
    if value is None:
        # None/Unit 值表示删除键
        return ('__DELETE__', 'none')
    elif isinstance(value, bool):
        return (str(value), 'bool')
    elif isinstance(value, int):
        return (str(value), 'int')
    elif isinstance(value, float):
        return (str(value), 'float')
    elif isinstance(value, str):
        return (value, 'string')
    elif isinstance(value, dict):
        return (json.dumps(value, ensure_ascii=False), 'map')
    elif isinstance(value, list):
        return (json.dumps(value, ensure_ascii=False), 'array')
    else:
        # 其他类型尝试 JSON 序列化
        try:
            return (json.dumps(value, ensure_ascii=False), 'string')
        except (TypeError, ValueError):
            return (str(value), 'string')


def deserialize_value(data: str, type_hint: str) -> Any:
    '''将序列化数据反序列化为 Python 值

    转换规则:
    - 'string' -> str
    - 'int' -> int(data)
    - 'float' -> float(data)
    - 'bool' -> data == 'True'
    - 'map' -> json.loads -> dict
    - 'array' -> json.loads -> list
    '''
    if type_hint == 'string':
        return data
    elif type_hint == 'int':
        return int(data)
    elif type_hint == 'float':
        return float(data)
    elif type_hint == 'bool':
        return data == 'True'
    elif type_hint == 'map':
        return json.loads(data)
    elif type_hint == 'array':
        return json.loads(data)
    else:
        # 未知类型，尝试 JSON 解析，失败则返回原始字符串
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data


# ==================== KVHandle ====================

class KVHandle:
    '''KV 存储句柄 — 对标 NTNT 的 KVStore Value

    属性:
    - _nexa_kv_id: 全局注册表 ID
    - db_type: 数据库类型 ('sqlite')
    - path: 数据库路径
    - connected: 是否已连接
    '''

    def __init__(self, kv_id: int, db_type: str = 'sqlite',
                 path: str = ':memory:', connected: bool = True):
        self._nexa_kv_id = kv_id
        self.db_type = db_type
        self.path = path
        self.connected = connected

    def to_dict(self) -> Dict:
        '''转换为字典格式'''
        return {
            '_nexa_kv_id': self._nexa_kv_id,
            'db_type': self.db_type,
            'path': self.path,
            'connected': self.connected,
        }

    def __repr__(self) -> str:
        return (f'KVHandle(_nexa_kv_id={self._nexa_kv_id}, '
                f'db_type={self.db_type}, path={self.path}, '
                f'connected={self.connected})')


# ==================== NexaKVStore ====================

class NexaKVStore:
    '''Nexa 统一 KV 存储 — SQLite backend

    表名: _nexa_kv（与 NTNT _kv 结构兼容但表名不同）

    通用 KV API（对标 NTNT 15函数）:
    - get/set/del/has/list/expire/ttl/flush/set_nx/incr
    - 类型化获取: get_int/get_str/get_json

    Agent-Native KV API:
    - agent_kv_query: 语义搜索 KV 数据
    - agent_kv_store: 带上下文存储
    - agent_kv_context: KV 数据注入 Agent 上下文
    '''

    def __init__(self, path: str = ':memory:'):
        '''初始化 KV 存储

        Args:
            path: 数据库路径。':memory:' 创建内存存储
        '''
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._create_table()

    def _create_table(self) -> None:
        '''创建 _nexa_kv 表和索引'''
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS _nexa_kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'string',
                expires_at INTEGER
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS _nexa_kv_expires
            ON _nexa_kv(expires_at) WHERE expires_at IS NOT NULL
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS _nexa_kv_prefix
            ON _nexa_kv(key)
        ''')
        self.conn.commit()

    def _cleanup_expired(self) -> None:
        '''清理过期键'''
        now = int(time.time())
        self.conn.execute(
            'DELETE FROM _nexa_kv WHERE expires_at IS NOT NULL AND expires_at <= ?',
            (now,)
        )
        self.conn.commit()

    def _get_raw(self, key: str) -> Optional[Tuple[str, str, Optional[int]]]:
        '''获取原始行数据 (value, type_hint, expires_at)，过期键返回 None'''
        now = int(time.time())
        row = self.conn.execute(
            'SELECT value, type, expires_at FROM _nexa_kv WHERE key = ? '
            'AND (expires_at IS NULL OR expires_at > ?)',
            (key, now)
        ).fetchone()
        return row

    # ===== Generic KV API =====

    def get(self, key: str, default: Any = None) -> Any:
        '''获取值，过期键返回 default'''
        with self._lock:
            self._cleanup_expired()
            row = self._get_raw(key)
            if row is None:
                return default
            return deserialize_value(row[0], row[1])

    def get_int(self, key: str, default: int = 0) -> int:
        '''类型化获取整数'''
        with self._lock:
            self._cleanup_expired()
            row = self._get_raw(key)
            if row is None:
                return default
            try:
                return int(row[0])
            except (ValueError, TypeError):
                return default

    def get_str(self, key: str, default: str = '') -> str:
        '''类型化获取字符串'''
        with self._lock:
            self._cleanup_expired()
            row = self._get_raw(key)
            if row is None:
                return default
            return row[0]

    def get_json(self, key: str) -> Optional[Dict]:
        '''JSON 解析获取，失败返回 None'''
        with self._lock:
            self._cleanup_expired()
            row = self._get_raw(key)
            if row is None:
                return None
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return None

    def set(self, key: str, value: Any, opts: Optional[Dict] = None) -> bool:
        '''设置值（opts 含 ttl），None/Unit = 删除键

        Args:
            key: 键名
            value: 值（None 表示删除键）
            opts: 可选参数，支持 {'ttl': 秒数}

        Returns:
            True 表示成功

        Raises:
            ContractViolation: 当数据库操作失败时（ensures 联动）
        '''
        with self._lock:
            self._cleanup_expired()
            try:
                serialized, type_hint = serialize_value(value)

                if type_hint == 'none':
                    # None/Unit 值 = 删除键
                    self.conn.execute(
                        'DELETE FROM _nexa_kv WHERE key = ?', (key,)
                    )
                    self.conn.commit()
                    return True

                # 计算 TTL
                ttl = None
                if opts and 'ttl' in opts:
                    ttl = opts['ttl']
                expires_at = None
                if ttl is not None:
                    expires_at = int(time.time()) + int(ttl)

                # UPSERT
                self.conn.execute('''
                    INSERT INTO _nexa_kv (key, value, type, expires_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        type = excluded.type,
                        expires_at = excluded.expires_at
                ''', (key, serialized, type_hint, expires_at))
                self.conn.commit()
                return True
            except sqlite3.DatabaseError as e:
                raise ContractViolation(
                    f'KV set failed for key "{key}": {e}',
                    clause_type='ensures',
                    context={'key': key, 'value': value, 'error': str(e)}
                )

    def set_nx(self, key: str, value: Any, opts: Optional[Dict] = None) -> bool:
        '''仅当不存在时设置（原子 NX 操作）

        实现要点（对标 NTNT）：
        1. 先删除过期键
        2. 再 INSERT OR IGNORE（键存在则不插入）
        3. 返回 True（成功设置）或 False（键已存在）

        Args:
            key: 键名
            value: 值
            opts: 可选参数，支持 {'ttl': 秒数}

        Returns:
            True 表示成功设置，False 表示键已存在
        '''
        with self._lock:
            now = int(time.time())
            # 1. 删除过期键
            self.conn.execute(
                'DELETE FROM _nexa_kv WHERE key = ? '
                'AND expires_at IS NOT NULL AND expires_at <= ?',
                (key, now)
            )
            self.conn.commit()

            # 2. INSERT OR IGNORE
            serialized, type_hint = serialize_value(value)
            if type_hint == 'none':
                # None 值不做 NX 设置
                return False

            ttl = None
            if opts and 'ttl' in opts:
                ttl = opts['ttl']
            expires_at = None
            if ttl is not None:
                expires_at = now + int(ttl)

            changes = self.conn.execute('''
                INSERT OR IGNORE INTO _nexa_kv (key, value, type, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (key, serialized, type_hint, expires_at)).rowcount
            self.conn.commit()

            # 3. 返回结果
            return changes > 0

    def del_key(self, key: str) -> bool:
        '''删除键

        Returns:
            True 表示键存在并已删除，False 表示键不存在
        '''
        with self._lock:
            self._cleanup_expired()
            changes = self.conn.execute(
                'DELETE FROM _nexa_kv WHERE key = ?', (key,)
            ).rowcount
            self.conn.commit()
            return changes > 0

    def has(self, key: str) -> bool:
        '''检查键是否存在（过期键 = 不存在）'''
        with self._lock:
            self._cleanup_expired()
            row = self.conn.execute(
                'SELECT 1 FROM _nexa_kv WHERE key = ? '
                'AND (expires_at IS NULL OR expires_at > ?)',
                (key, int(time.time()))
            ).fetchone()
            return row is not None

    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        '''列出键（前缀过滤）'''
        with self._lock:
            self._cleanup_expired()
            if prefix:
                rows = self.conn.execute(
                    'SELECT key FROM _nexa_kv WHERE key LIKE ? ESCAPE "\\" '
                    'AND (expires_at IS NULL OR expires_at > ?) ORDER BY key',
                    (prefix.replace('%', '\\%').replace('_', '\\_') + '%',
                     int(time.time()))
                ).fetchall()
            else:
                rows = self.conn.execute(
                    'SELECT key FROM _nexa_kv '
                    'WHERE expires_at IS NULL OR expires_at > ? ORDER BY key',
                    (int(time.time()),)
                ).fetchall()
            return [row[0] for row in rows]

    def expire(self, key: str, ttl_seconds: int) -> bool:
        '''设置过期时间

        Args:
            key: 键名
            ttl_seconds: TTL 秒数

        Returns:
            True 表示成功设置，False 表示键不存在
        '''
        with self._lock:
            self._cleanup_expired()
            now = int(time.time())
            expires_at = now + ttl_seconds
            changes = self.conn.execute(
                'UPDATE _nexa_kv SET expires_at = ? WHERE key = ? '
                'AND (expires_at IS NULL OR expires_at > ?)',
                (expires_at, key, now)
            ).rowcount
            self.conn.commit()
            return changes > 0

    def ttl(self, key: str) -> Optional[int]:
        '''查看剩余 TTL 秒数

        Returns:
            剩余 TTL 秒数，None 表示键不存在或永不过期
        '''
        with self._lock:
            self._cleanup_expired()
            now = int(time.time())
            row = self.conn.execute(
                'SELECT expires_at FROM _nexa_kv WHERE key = ? '
                'AND (expires_at IS NULL OR expires_at > ?)',
                (key, now)
            ).fetchone()
            if row is None:
                return None  # 键不存在
            if row[0] is None:
                return None  # 永不过期
            remaining = row[0] - now
            return remaining

    def flush(self) -> bool:
        '''清空所有键'''
        with self._lock:
            self.conn.execute('DELETE FROM _nexa_kv')
            self.conn.commit()
            return True

    def incr(self, key: str, amount: int = 1) -> int:
        '''原子递增（保留 TTL）

        实现要点（对标 NTNT）：
        1. 不存在键：从 amount 开始创建
        2. 存在键：读取当前值 + amount
        3. 保留已有 TTL（如果有的话）
        4. 非整数键 -> TypeError

        Args:
            key: 键名
            amount: 递增量（可为负数用于递减）

        Returns:
            递增后的新值

        Raises:
            TypeError: 键存在但值非整数
        '''
        with self._lock:
            now = int(time.time())
            row = self.conn.execute(
                'SELECT value, type, expires_at FROM _nexa_kv WHERE key = ? '
                'AND (expires_at IS NULL OR expires_at > ?)',
                (key, now)
            ).fetchone()

            if row is None:
                # 键不存在或已过期，从 amount 开始创建
                self.conn.execute('''
                    INSERT INTO _nexa_kv (key, value, type, expires_at)
                    VALUES (?, ?, 'int', NULL)
                ''', (key, str(amount)))
                self.conn.commit()
                return amount

            # 键存在，验证当前值是否为整数
            current_value = row[0]
            current_type = row[1]
            current_expires_at = row[2]

            try:
                current = int(current_value)
            except (ValueError, TypeError):
                raise TypeError(
                    f'KV incr failed: key "{key}" has non-integer value '
                    f'(type={current_type}, value={current_value})'
                )

            new_val = current + amount
            self.conn.execute('''
                UPDATE _nexa_kv SET value = ? WHERE key = ?
            ''', (str(new_val), key))
            self.conn.commit()
            return new_val

    # ===== Agent-Native KV API =====

    def agent_kv_query(self, semantic_query: str) -> List[Dict]:
        '''语义搜索 KV 数据（简单关键词匹配）

        Args:
            semantic_query: 语义查询字符串

        Returns:
            匹配的 KV 数据列表，每项包含 key/value/type
        '''
        with self._lock:
            self._cleanup_expired()
            now = int(time.time())

            # 简单关键词匹配：拆分查询词，匹配键名或值
            keywords = semantic_query.lower().split()

            if not keywords:
                # 空查询返回所有键
                rows = self.conn.execute(
                    'SELECT key, value, type FROM _nexa_kv '
                    'WHERE expires_at IS NULL OR expires_at > ? ORDER BY key',
                    (now,)
                ).fetchall()
            else:
                # 构建 LIKE 条件
                conditions = []
                params = []
                for kw in keywords:
                    conditions.append('(LOWER(key) LIKE ? OR LOWER(value) LIKE ?)')
                    params.extend([f'%{kw}%', f'%{kw}%'])

                where_clause = ' AND '.join(conditions) if len(conditions) > 1 else conditions[0]
                params.append(now)

                rows = self.conn.execute(
                    f'SELECT key, value, type FROM _nexa_kv '
                    f'WHERE ({where_clause}) AND (expires_at IS NULL OR expires_at > ?) '
                    f'ORDER BY key',
                    params
                ).fetchall()

            results = []
            for row in rows:
                results.append({
                    'key': row[0],
                    'value': deserialize_value(row[1], row[2]),
                    'type': row[2],
                })
            return results

    def agent_kv_store(self, key: str, value: Any,
                       context: Optional[Dict] = None) -> bool:
        '''带上下文存储

        Args:
            key: 键名
            value: 值
            context: 上下文信息（存储为元数据前缀键）

        Returns:
            True 表示成功
        '''
        # 存储主键值
        result = self.set(key, value)

        # 如果有上下文，存储为 _ctx: 前缀键
        if context and result:
            ctx_key = f'_ctx:{key}'
            self.set(ctx_key, context)

        return result

    def agent_kv_context(self, agent: Any) -> Dict:
        '''KV 数据注入 Agent 上下文

        Args:
            agent: Agent 对象（需要有 name 属性）

        Returns:
            包含 KV 数据的上下文字典
        '''
        agent_name = ''
        if isinstance(agent, dict):
            agent_name = agent.get('name', '')
        elif hasattr(agent, 'name'):
            agent_name = agent.name
        elif isinstance(agent, str):
            agent_name = agent

        context = {
            'agent_name': agent_name,
            'kv_keys': self.list_keys(),
            'kv_count': len(self.list_keys()),
        }

        # 注入与 agent 相关的键值
        agent_prefix = f'agent:{agent_name}:'
        agent_keys = self.list_keys(prefix=agent_prefix)
        if agent_keys:
            context['agent_kv_data'] = {}
            for k in agent_keys:
                context['agent_kv_data'][k] = self.get(k)

        # 注入上下文元数据
        ctx_prefix = '_ctx:'
        ctx_keys = self.list_keys(prefix=ctx_prefix)
        if ctx_keys:
            context['kv_contexts'] = {}
            for k in ctx_keys:
                context['kv_contexts'][k[len(ctx_prefix):]] = self.get_json(k)

        return context

    def close(self) -> None:
        '''关闭 KV 存储连接'''
        with self._lock:
            if self.conn:
                self.conn.close()
                self.conn = None


# ==================== 顶层函数 API ====================

def kv_open(path: str = ':memory:') -> KVHandle:
    '''打开/创建 KV 存储

    Args:
        path: 数据库路径。':memory:' 创建内存存储

    Returns:
        KVHandle 句柄
    '''
    store = NexaKVStore(path)
    kv_id = _next_kv_id()
    _register_kv(kv_id, store)
    return KVHandle(kv_id, db_type='sqlite', path=path, connected=True)


def _resolve_store(kv: Any) -> NexaKVStore:
    '''从 KVHandle 或直接传入 NexaKVStore 获取存储实例'''
    if isinstance(kv, KVHandle):
        store = _get_kv_store(kv._nexa_kv_id)
        if store is None:
            raise ContractViolation(
                f'KV store not found: id={kv._nexa_kv_id}',
                clause_type='requires',
                context={'kv_id': kv._nexa_kv_id}
            )
        return store
    elif isinstance(kv, NexaKVStore):
        return kv
    elif isinstance(kv, dict):
        kv_id = kv.get('_nexa_kv_id')
        if kv_id is None:
            raise ContractViolation(
                'KV handle dict missing _nexa_kv_id',
                clause_type='requires'
            )
        store = _get_kv_store(kv_id)
        if store is None:
            raise ContractViolation(
                f'KV store not found: id={kv_id}',
                clause_type='requires',
                context={'kv_id': kv_id}
            )
        return store
    else:
        raise TypeError(f'Invalid KV handle type: {type(kv)}')


def kv_get(kv: Any, key: str, default: Any = None) -> Any:
    '''获取值，过期键返回 default'''
    return _resolve_store(kv).get(key, default)


def kv_get_int(kv: Any, key: str, default: int = 0) -> int:
    '''类型化获取整数'''
    return _resolve_store(kv).get_int(key, default)


def kv_get_str(kv: Any, key: str, default: str = '') -> str:
    '''类型化获取字符串'''
    return _resolve_store(kv).get_str(key, default)


def kv_get_json(kv: Any, key: str) -> Optional[Dict]:
    '''JSON 解析获取'''
    return _resolve_store(kv).get_json(key)


def kv_set(kv: Any, key: str, value: Any, opts: Optional[Dict] = None) -> bool:
    '''设置值（opts 含 ttl），None/Unit = 删除键'''
    return _resolve_store(kv).set(key, value, opts)


def kv_set_nx(kv: Any, key: str, value: Any, opts: Optional[Dict] = None) -> bool:
    '''仅当不存在时设置（原子 NX）'''
    return _resolve_store(kv).set_nx(key, value, opts)


def kv_del(kv: Any, key: str) -> bool:
    '''删除键'''
    return _resolve_store(kv).del_key(key)


def kv_has(kv: Any, key: str) -> bool:
    '''检查键是否存在'''
    return _resolve_store(kv).has(key)


def kv_list(kv: Any, prefix: Optional[str] = None) -> List[str]:
    '''列出键（前缀过滤）'''
    return _resolve_store(kv).list_keys(prefix)


def kv_expire(kv: Any, key: str, ttl_seconds: int) -> bool:
    '''设置过期时间'''
    return _resolve_store(kv).expire(key, ttl_seconds)


def kv_ttl(kv: Any, key: str) -> Optional[int]:
    '''查看剩余 TTL 秒数'''
    return _resolve_store(kv).ttl(key)


def kv_flush(kv: Any) -> bool:
    '''清空所有键'''
    return _resolve_store(kv).flush()


def kv_incr(kv: Any, key: str, amount: int = 1) -> int:
    '''原子递增（保留 TTL）'''
    return _resolve_store(kv).incr(key, amount)


# ===== Agent-Native 顶层函数 =====

def agent_kv_query(kv: Any, semantic_query: str) -> List[Dict]:
    '''语义搜索 KV 数据'''
    return _resolve_store(kv).agent_kv_query(semantic_query)


def agent_kv_store(kv: Any, key: str, value: Any,
                   context: Optional[Dict] = None) -> bool:
    '''带上下文存储'''
    return _resolve_store(kv).agent_kv_store(key, value, context)


def agent_kv_context(kv: Any, agent: Any) -> Dict:
    '''KV 数据注入 Agent 上下文'''
    return _resolve_store(kv).agent_kv_context(agent)