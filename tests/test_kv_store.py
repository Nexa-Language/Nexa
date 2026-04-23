'''
P2-3: KV Store 测试 — 50+ 测试覆盖全部功能

测试类:
- TestKVOpen (4): open/in-memory/registry/handle
- TestKVGetSet (8): 基本CRUD/类型保持/None删除
- TestKVTypedGet (6): get_int/get_str/get_json/default
- TestKVSetNX (5): NX原子操作/过期键处理/TTL
- TestKVDeleteHas (4): del/has/过期键
- TestKVList (4): list/前缀过滤/空存储
- TestKVExpireTTL (5): expire/ttl/过期清理
- TestKVFlush (2): 清空所有键
- TestKVIncr (6): 递增/递减/不存在键/TTL保留
- TestKVSerialization (4): 序列化/反序列化/类型提示
- TestKVContractViolation (3): 错误→契约联动
- TestAgentKV (4): 语义查询/上下文存储/Agent注入
- TestKVNamespace (4): stdlib注册/调用
- TestKVParserAST (3): kv_decl解析
'''

import pytest
import json
import time
import threading
import os

from src.runtime.kv_store import (
    NexaKVStore, KVHandle,
    kv_open, kv_get, kv_get_int, kv_get_str, kv_get_json,
    kv_set, kv_set_nx, kv_del, kv_has, kv_list,
    kv_expire, kv_ttl, kv_flush, kv_incr,
    agent_kv_query, agent_kv_store, agent_kv_context,
    serialize_value, deserialize_value,
    _next_kv_id, _register_kv, _unregister_kv, _get_kv_store,
    get_active_kv_stores, _kv_registry, _registry_lock,
)
from src.runtime.contracts import ContractViolation


# ==================== TestKVOpen ====================

class TestKVOpen:
    '''KV open/in-memory/registry/handle 测试'''

    def test_kv_open_memory(self):
        '''打开内存 KV 存储'''
        handle = kv_open(':memory:')
        assert isinstance(handle, KVHandle)
        assert handle.db_type == 'sqlite'
        assert handle.path == ':memory:'
        assert handle.connected is True

    def test_kv_open_file(self):
        '''打开文件 KV 存储'''
        path = '/tmp/test_kv_open_file.db'
        # 清理旧文件
        if os.path.exists(path):
            os.remove(path)
        handle = kv_open(path)
        assert isinstance(handle, KVHandle)
        assert handle.path == path
        assert handle.connected is True
        # 清理
        os.remove(path)

    def test_kv_registry(self):
        '''KV 注册表 ID 递增'''
        h1 = kv_open(':memory:')
        h2 = kv_open(':memory:')
        assert h2._nexa_kv_id > h1._nexa_kv_id

    def test_kv_handle_to_dict(self):
        '''KVHandle 转字典格式'''
        handle = kv_open(':memory:')
        d = handle.to_dict()
        assert '_nexa_kv_id' in d
        assert d['db_type'] == 'sqlite'
        assert d['path'] == ':memory:'
        assert d['connected'] is True


# ==================== TestKVGetSet ====================

class TestKVGetSet:
    '''基本 CRUD / 类型保持 / None 删除 测试'''

    def setup_method(self):
        self.store = NexaKVStore(':memory:')
        self.handle = kv_open(':memory:')

    def test_set_get_string(self):
        '''设置和获取字符串'''
        self.store.set('key1', 'hello')
        result = self.store.get('key1')
        assert result == 'hello'

    def test_set_get_int(self):
        '''设置和获取整数'''
        self.store.set('key2', 42)
        result = self.store.get('key2')
        assert result == 42

    def test_set_get_float(self):
        '''设置和获取浮点数'''
        self.store.set('key3', 3.14)
        result = self.store.get('key3')
        assert result == 3.14

    def test_set_get_bool(self):
        '''设置和获取布尔值'''
        self.store.set('key4', True)
        result = self.store.get('key4')
        assert result is True

    def test_set_get_dict(self):
        '''设置和获取字典'''
        val = {'name': 'Alice', 'age': 30}
        self.store.set('key5', val)
        result = self.store.get('key5')
        assert result == val

    def test_set_get_list(self):
        '''设置和获取列表'''
        val = [1, 2, 3]
        self.store.set('key6', val)
        result = self.store.get('key6')
        assert result == val

    def test_set_none_deletes_key(self):
        '''设置 None 值等同于删除键'''
        self.store.set('key7', 'value')
        assert self.store.has('key7') is True
        self.store.set('key7', None)
        assert self.store.has('key7') is False

    def test_get_nonexistent_key_returns_default(self):
        '''获取不存在键返回默认值'''
        result = self.store.get('nonexistent', 'default_val')
        assert result == 'default_val'


# ==================== TestKVTypedGet ====================

class TestKVTypedGet:
    '''get_int/get_str/get_json/default 测试'''

    def setup_method(self):
        self.store = NexaKVStore(':memory:')

    def test_get_int_success(self):
        '''get_int 正常获取整数'''
        self.store.set('count', 100)
        result = self.store.get_int('count')
        assert result == 100

    def test_get_int_default(self):
        '''get_int 不存在键返回默认0'''
        result = self.store.get_int('missing')
        assert result == 0

    def test_get_int_custom_default(self):
        '''get_int 自定义默认值'''
        result = self.store.get_int('missing', default=-1)
        assert result == -1

    def test_get_str_success(self):
        '''get_str 正常获取字符串'''
        self.store.set('name', 'Alice')
        result = self.store.get_str('name')
        assert result == 'Alice'

    def test_get_str_default(self):
        '''get_str 不存在键返回默认空字符串'''
        result = self.store.get_str('missing')
        assert result == ''

    def test_get_json_success(self):
        '''get_json 正常获取字典'''
        self.store.set('user', {'name': 'Bob', 'age': 25})
        result = self.store.get_json('user')
        assert result == {'name': 'Bob', 'age': 25}

    def test_get_json_none_default(self):
        '''get_json 不存在键返回 None'''
        result = self.store.get_json('missing')
        assert result is None


# ==================== TestKVSetNX ====================

class TestKVSetNX:
    '''NX 原子操作 / 过期键处理 / TTL 测试'''

    def setup_method(self):
        self.store = NexaKVStore(':memory:')

    def test_set_nx_success(self):
        '''set_nx 成功设置不存在键'''
        result = self.store.set_nx('lock:1', 'worker-1')
        assert result is True
        assert self.store.get('lock:1') == 'worker-1'

    def test_set_nx_fail_existing(self):
        '''set_nx 键已存在返回 False'''
        self.store.set('lock:1', 'worker-1')
        result = self.store.set_nx('lock:1', 'worker-2')
        assert result is False
        # 值不变
        assert self.store.get('lock:1') == 'worker-1'

    def test_set_nx_with_ttl(self):
        '''set_nx 带 TTL'''
        result = self.store.set_nx('lock:2', 'worker-1', opts={'ttl': 60})
        assert result is True
        ttl = self.store.ttl('lock:2')
        assert ttl is not None
        assert 55 <= ttl <= 65

    def test_set_nx_expired_key(self):
        '''set_nx 对已过期键可重新设置'''
        # 先设置一个很快过期的键
        self.store.set('lock:3', 'old_value', opts={'ttl': 1})
        # 等待过期
        time.sleep(1.5)
        result = self.store.set_nx('lock:3', 'new_value')
        assert result is True

    def test_set_nx_none_value(self):
        '''set_nx 对 None 值不做设置'''
        result = self.store.set_nx('key', None)
        assert result is False


# ==================== TestKVDeleteHas ====================

class TestKVDeleteHas:
    '''del / has / 过期键 测试'''

    def setup_method(self):
        self.store = NexaKVStore(':memory:')

    def test_del_existing_key(self):
        '''删除存在键返回 True'''
        self.store.set('key1', 'value')
        result = self.store.del_key('key1')
        assert result is True
        assert self.store.has('key1') is False

    def test_del_nonexistent_key(self):
        '''删除不存在键返回 False'''
        result = self.store.del_key('nonexistent')
        assert result is False

    def test_has_existing_key(self):
        '''has 检查存在键'''
        self.store.set('key2', 'value')
        assert self.store.has('key2') is True

    def test_has_expired_key(self):
        '''has 检查过期键返回 False'''
        self.store.set('key3', 'value', opts={'ttl': 1})
        time.sleep(1.5)
        assert self.store.has('key3') is False


# ==================== TestKVList ====================

class TestKVList:
    '''list / 前缀过滤 / 空存储 测试'''

    def setup_method(self):
        self.store = NexaKVStore(':memory:')

    def test_list_all_keys(self):
        '''列出所有键'''
        self.store.set('a', 1)
        self.store.set('b', 2)
        self.store.set('c', 3)
        keys = self.store.list_keys()
        assert sorted(keys) == ['a', 'b', 'c']

    def test_list_prefix_filter(self):
        '''前缀过滤键'''
        self.store.set('user:1', 'Alice')
        self.store.set('user:2', 'Bob')
        self.store.set('session:1', 'token')
        keys = self.store.list_keys(prefix='user:')
        assert sorted(keys) == ['user:1', 'user:2']

    def test_list_empty_store(self):
        '''空存储返回空列表'''
        keys = self.store.list_keys()
        assert keys == []

    def test_list_excludes_expired(self):
        '''列出键排除过期键'''
        self.store.set('active', 'value')
        self.store.set('expired', 'value', opts={'ttl': 1})
        time.sleep(1.5)
        keys = self.store.list_keys()
        assert 'active' in keys
        assert 'expired' not in keys


# ==================== TestKVExpireTTL ====================

class TestKVExpireTTL:
    '''expire / ttl / 过期清理 测试'''

    def setup_method(self):
        self.store = NexaKVStore(':memory:')

    def test_expire_success(self):
        '''expire 设置过期时间'''
        self.store.set('key1', 'value')
        result = self.store.expire('key1', 60)
        assert result is True

    def test_expire_nonexistent_key(self):
        '''expire 对不存在键返回 False'''
        result = self.store.expire('nonexistent', 60)
        assert result is False

    def test_ttl_with_expiry(self):
        '''ttl 查看带 TTL 的键'''
        self.store.set('key2', 'value', opts={'ttl': 300})
        ttl = self.store.ttl('key2')
        assert ttl is not None
        assert 295 <= ttl <= 305

    def test_ttl_no_expiry(self):
        '''ttl 查看永不过期的键返回 None'''
        self.store.set('key3', 'value')
        ttl = self.store.ttl('key3')
        assert ttl is None

    def test_ttl_nonexistent_key(self):
        '''ttl 查看不存在键返回 None'''
        ttl = self.store.ttl('nonexistent')
        assert ttl is None


# ==================== TestKVFlush ====================

class TestKVFlush:
    '''清空所有键 测试'''

    def setup_method(self):
        self.store = NexaKVStore(':memory:')

    def test_flush_clears_all(self):
        '''flush 清空所有键'''
        self.store.set('a', 1)
        self.store.set('b', 2)
        self.store.set('c', 3)
        result = self.store.flush()
        assert result is True
        keys = self.store.list_keys()
        assert keys == []

    def test_flush_empty_store(self):
        '''flush 空存储仍返回 True'''
        result = self.store.flush()
        assert result is True


# ==================== TestKVIncr ====================

class TestKVIncr:
    '''递增 / 递减 / 不存在键 / TTL保留 测试'''

    def setup_method(self):
        self.store = NexaKVStore(':memory:')

    def test_incr_from_zero(self):
        '''incr 不存在键从 amount 开始'''
        result = self.store.incr('counter', 1)
        assert result == 1

    def test_incr_existing_key(self):
        '''incr 存在键递增'''
        self.store.set('counter', 5)
        result = self.store.incr('counter', 3)
        assert result == 8

    def test_incr_negative(self):
        '''incr 负数递减'''
        self.store.set('counter', 10)
        result = self.store.incr('counter', -3)
        assert result == 7

    def test_incr_default_amount(self):
        '''incr 默认 amount=1'''
        result = self.store.incr('counter')
        assert result == 1
        result = self.store.incr('counter')
        assert result == 2

    def test_incr_non_integer_raises_type_error(self):
        '''incr 对非整数键抛出 TypeError'''
        self.store.set('str_key', 'not_a_number')
        with pytest.raises(TypeError):
            self.store.incr('str_key', 1)

    def test_incr_preserves_ttl(self):
        '''incr 保留已有 TTL'''
        self.store.set('counter', 0, opts={'ttl': 300})
        ttl_before = self.store.ttl('counter')
        self.store.incr('counter', 5)
        ttl_after = self.store.ttl('counter')
        assert ttl_after is not None
        # TTL 应大致保持不变（允许1秒误差）
        assert abs(ttl_before - ttl_after) <= 2


# ==================== TestKVSerialization ====================

class TestKVSerialization:
    '''序列化 / 反序列化 / 类型提示 测试'''

    def test_serialize_string(self):
        '''序列化字符串'''
        data, type_hint = serialize_value('hello')
        assert data == 'hello'
        assert type_hint == 'string'

    def test_serialize_int(self):
        '''序列化整数'''
        data, type_hint = serialize_value(42)
        assert data == '42'
        assert type_hint == 'int'

    def test_serialize_deserialize_dict(self):
        '''序列化/反序列化字典'''
        val = {'name': 'Alice', 'age': 30}
        data, type_hint = serialize_value(val)
        assert type_hint == 'map'
        result = deserialize_value(data, type_hint)
        assert result == val

    def test_deserialize_all_types(self):
        '''反序列化所有类型'''
        assert deserialize_value('hello', 'string') == 'hello'
        assert deserialize_value('42', 'int') == 42
        assert deserialize_value('3.14', 'float') == 3.14
        assert deserialize_value('True', 'bool') is True
        assert deserialize_value('False', 'bool') is False
        assert deserialize_value('[1,2,3]', 'array') == [1, 2, 3]


# ==================== TestKVContractViolation ====================

class TestKVContractViolation:
    '''错误 → 契约联动 测试'''

    def setup_method(self):
        self.store = NexaKVStore(':memory:')
        self.handle = kv_open(':memory:')

    def test_resolve_store_invalid_handle(self):
        '''无效 KV Handle 类型抛出 TypeError'''
        with pytest.raises(TypeError):
            from src.runtime.kv_store import _resolve_store
            _resolve_store(12345)

    def test_resolve_store_missing_kv_id(self):
        '''KV Handle dict 缺少 _nexa_kv_id 抛出 ContractViolation'''
        with pytest.raises(ContractViolation):
            from src.runtime.kv_store import _resolve_store
            _resolve_store({'no_id': True})

    def test_incr_non_int_triggers_contract(self):
        '''incr 非整数键 → TypeError（可映射到 ContractViolation requires）'''
        self.store.set('str_key', 'abc')
        with pytest.raises(TypeError):
            self.store.incr('str_key', 1)


# ==================== TestAgentKV ====================

class TestAgentKV:
    '''语义查询 / 上下文存储 / Agent 注入 测试'''

    def setup_method(self):
        self.store = NexaKVStore(':memory:')

    def test_agent_kv_query_keyword(self):
        '''agent_kv_query 关键词搜索'''
        self.store.set('user:alice', {'name': 'Alice', 'role': 'admin'})
        self.store.set('user:bob', {'name': 'Bob', 'role': 'user'})
        self.store.set('config:theme', 'dark')
        results = self.store.agent_kv_query('alice')
        assert len(results) >= 1
        assert any(r['key'] == 'user:alice' for r in results)

    def test_agent_kv_query_empty(self):
        '''agent_kv_query 空查询返回所有键'''
        self.store.set('key1', 'val1')
        self.store.set('key2', 'val2')
        results = self.store.agent_kv_query('')
        assert len(results) == 2

    def test_agent_kv_store_with_context(self):
        '''agent_kv_store 带上下文存储'''
        result = self.store.agent_kv_store(
            'important_data', 'value123',
            context={'source': 'api', 'timestamp': '2026-01-01'}
        )
        assert result is True
        assert self.store.get('important_data') == 'value123'
        ctx = self.store.get_json('_ctx:important_data')
        assert ctx is not None

    def test_agent_kv_context_injection(self):
        '''agent_kv_context 注入 Agent 上下文'''
        self.store.set('agent:cacheBot:memory', 'some data')
        context = self.store.agent_kv_context({'name': 'cacheBot'})
        assert context['agent_name'] == 'cacheBot'
        assert 'kv_keys' in context
        assert 'kv_count' in context


# ==================== TestKVNamespace ====================

class TestKVNamespace:
    '''stdlib 注册 / 调用 测试'''

    def test_std_namespace_map_has_kv(self):
        '''STD_NAMESPACE_MAP 包含 std.kv'''
        from src.runtime.stdlib import STD_NAMESPACE_MAP
        assert 'std.kv' in STD_NAMESPACE_MAP

    def test_std_kv_namespace_17_tools(self):
        '''std.kv namespace 包含 17 个工具'''
        from src.runtime.stdlib import STD_NAMESPACE_MAP
        kv_tools = STD_NAMESPACE_MAP['std.kv']
        assert len(kv_tools) == 17

    def test_stdlib_tools_include_kv(self):
        '''stdlib 工具包含 KV 工具'''
        from src.runtime.stdlib import get_stdlib_tools
        tools = get_stdlib_tools()
        assert 'std_kv_open' in tools
        assert 'std_kv_get' in tools
        assert 'std_kv_set' in tools
        assert 'std_kv_incr' in tools

    def test_std_kv_open_handler(self):
        '''std_kv_open handler 工作正常'''
        from src.runtime.stdlib import get_stdlib_tool
        tool = get_stdlib_tool('std_kv_open')
        assert tool is not None
        result = tool.execute(path=':memory:')
        # 结果应该是 KVHandle JSON
        parsed = json.loads(result)
        assert '_nexa_kv_id' in parsed
        assert parsed['db_type'] == 'sqlite'


# ==================== TestKVParserAST ====================

class TestKVParserAST:
    '''kv_decl 解析 / AST 测试'''

    def test_parse_kv_decl(self):
        '''解析 kv 声明'''
        from src.nexa_parser import parse
        code = 'kv myCache = open(":memory:")'
        ast = parse(code)
        body = ast.get('body', [])
        assert len(body) >= 1
        kv_node = body[0]
        assert kv_node.get('type') == 'KVDeclaration'
        assert kv_node.get('name') == 'myCache'
        assert kv_node.get('path') == ':memory:'

    def test_parse_kv_decl_file_path(self):
        '''解析 kv 声明（文件路径）'''
        from src.nexa_parser import parse
        code = 'kv appCache = open("cache.db")'
        ast = parse(code)
        body = ast.get('body', [])
        kv_node = body[0]
        assert kv_node.get('type') == 'KVDeclaration'
        assert kv_node.get('path') == 'cache.db'

    def test_ast_transformer_kv_decl(self):
        '''AST Transformer 处理 kv_decl'''
        from src.ast_transformer import NexaTransformer
        from lark import Tree
        transformer = NexaTransformer()
        tree = Tree('kv_decl', ['myKV', '"data.db"'])
        result = transformer.kv_decl(tree.children)
        assert result['type'] == 'KVDeclaration'
        assert result['name'] == 'myKV'
        assert result['path'] == 'data.db'


# ==================== TestKVTopLevelFunctions ====================

class TestKVTopLevelFunctions:
    '''顶层函数 API 测试'''

    def setup_method(self):
        self.handle = kv_open(':memory:')

    def test_kv_get_via_handle(self):
        '''通过 KVHandle 顶层函数获取值'''
        kv_set(self.handle, 'key1', 'value1')
        result = kv_get(self.handle, 'key1')
        assert result == 'value1'

    def test_kv_set_via_handle(self):
        '''通过 KVHandle 顶层函数设置值'''
        result = kv_set(self.handle, 'key2', 42)
        assert result is True
        assert kv_get(self.handle, 'key2') == 42

    def test_kv_del_via_handle(self):
        '''通过 KVHandle 顶层函数删除键'''
        kv_set(self.handle, 'key3', 'val')
        result = kv_del(self.handle, 'key3')
        assert result is True

    def test_kv_has_via_handle(self):
        '''通过 KVHandle 顶层函数检查键'''
        kv_set(self.handle, 'key4', 'val')
        assert kv_has(self.handle, 'key4') is True
        assert kv_has(self.handle, 'missing') is False

    def test_kv_list_via_handle(self):
        '''通过 KVHandle 顶层函数列出键'''
        kv_set(self.handle, 'a', 1)
        kv_set(self.handle, 'b', 2)
        keys = kv_list(self.handle)
        assert sorted(keys) == ['a', 'b']

    def test_kv_incr_via_handle(self):
        '''通过 KVHandle 顶层函数递增'''
        result = kv_incr(self.handle, 'counter', 5)
        assert result == 5
        result = kv_incr(self.handle, 'counter', 3)
        assert result == 8

    def test_kv_get_int_via_handle(self):
        '''通过 KVHandle 顶层函数获取整数'''
        kv_set(self.handle, 'count', 100)
        result = kv_get_int(self.handle, 'count')
        assert result == 100

    def test_kv_get_str_via_handle(self):
        '''通过 KVHandle 顶层函数获取字符串'''
        kv_set(self.handle, 'name', 'Alice')
        result = kv_get_str(self.handle, 'name')
        assert result == 'Alice'

    def test_kv_get_json_via_handle(self):
        '''通过 KVHandle 顶层函数获取 JSON'''
        kv_set(self.handle, 'data', {'key': 'val'})
        result = kv_get_json(self.handle, 'data')
        assert result == {'key': 'val'}

    def test_kv_set_nx_via_handle(self):
        '''通过 KVHandle 顶层函数 NX 设置'''
        result = kv_set_nx(self.handle, 'lock', 'worker')
        assert result is True
        result = kv_set_nx(self.handle, 'lock', 'worker2')
        assert result is False

    def test_kv_expire_ttl_via_handle(self):
        '''通过 KVHandle 顶层函数设置过期和查看 TTL'''
        kv_set(self.handle, 'session', 'token', opts={'ttl': 300})
        result = kv_expire(self.handle, 'session', 600)
        assert result is True
        ttl = kv_ttl(self.handle, 'session')
        assert ttl is not None

    def test_kv_flush_via_handle(self):
        '''通过 KVHandle 顶层函数清空'''
        kv_set(self.handle, 'a', 1)
        kv_set(self.handle, 'b', 2)
        result = kv_flush(self.handle)
        assert result is True
        assert kv_list(self.handle) == []


# ==================== TestKVThreadSafety ====================

class TestKVThreadSafety:
    '''线程安全 测试'''

    def test_concurrent_set_get(self):
        '''并发 set/get 不出错'''
        store = NexaKVStore(':memory:')
        errors = []

        def writer(i):
            try:
                for j in range(10):
                    store.set(f'key_{i}_{j}', f'val_{i}_{j}')
            except Exception as e:
                errors.append(e)

        def reader(i):
            try:
                for j in range(10):
                    store.get(f'key_{i}_{j}')
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_incr(self):
        '''并发 incr 结果一致'''
        store = NexaKVStore(':memory:')
        store.set('counter', 0)
        errors = []

        def increment():
            try:
                for _ in range(10):
                    store.incr('counter', 1)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=increment))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # 最终值应该是 50 (5 threads * 10 increments)
        assert store.get_int('counter') == 50


# ==================== TestKVRegistry ====================

class TestKVRegistry:
    '''注册表管理 测试'''

    def test_register_unregister(self):
        '''注册和取消注册 KV 存储'''
        store = NexaKVStore(':memory:')
        kv_id = _next_kv_id()
        _register_kv(kv_id, store)
        assert _get_kv_store(kv_id) is store

        _unregister_kv(kv_id)
        assert _get_kv_store(kv_id) is None

    def test_get_active_kv_stores(self):
        '''获取活跃 KV 存储快照'''
        h1 = kv_open(':memory:')
        h2 = kv_open(':memory:')
        active = get_active_kv_stores()
        assert h1._nexa_kv_id in active
        assert h2._nexa_kv_id in active

    def test_resolve_store_from_handle(self):
        '''从 KVHandle 解析存储'''
        handle = kv_open(':memory:')
        from src.runtime.kv_store import _resolve_store
        store = _resolve_store(handle)
        assert isinstance(store, NexaKVStore)

    def test_resolve_store_from_dict(self):
        '''从字典 KVHandle 解析存储'''
        handle = kv_open(':memory:')
        from src.runtime.kv_store import _resolve_store
        store = _resolve_store(handle.to_dict())
        assert isinstance(store, NexaKVStore)