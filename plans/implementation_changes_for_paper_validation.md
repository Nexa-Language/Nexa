# Nexa 实现修改计划 - 使论文性能声明可验证

## 核心问题分析

### 问题 1: Python SDK Agent.clone() 不是 COW

**当前实现** (`src/runtime/agent.py:327-356`):
```python
def clone(self, new_name: str, **kwargs):
    # 创建全新实例，复制所有属性
    return NexaAgent(
        name=new_name,
        prompt=prompt,
        tools=tools,
        ...
    )
```

**问题**: 这是深拷贝，不是 Copy-on-Write。论文声称的 200,000x 性能提升来自 COW。

**解决方案**:

方案 A: 在 Python 中实现真正的 COW Agent
- 创建 `CowAgentState` 类来管理共享状态
- `clone()` 只创建新的引用，不复制数据
- 修改时才创建本地副本

方案 B: 通过 FFI 调用 Rust AVM 的 COW
- 扩展 `avm/src/ffi/python.rs` 添加 COW 接口
- Python SDK 调用 Rust COW 实现

**推荐方案 A**: 纯 Python 实现，更简单且与现有架构兼容。

### 问题 2: Python SDK 缓存语义匹配未生效

**当前实现** (`src/runtime/cache_manager.py:245-266`):
```python
# 语义匹配 - 使用关键词哈希
semantic_hash = self._generate_semantic_hash(last_user_msg)
if semantic_hash in self._semantic_index:
    for similar_key in self._semantic_index[semantic_hash]:
        ...
```

**问题**: `_generate_semantic_hash` 使用简单的关键词提取，可能无法有效匹配相似语义。

**解决方案**:
- 改进语义哈希算法
- 使用 embedding 相似度而非关键词哈希
- 或保持现有实现，在测试中验证真实命中率

### 问题 3: WASM 和 Work-Stealing 仅在 Rust AVM

**现状**: 这些特性在 Rust AVM 中实现，Python SDK 不使用。

**解决方案**: 
- 论文声明需要明确适用范围
- 或为 Python SDK 添加 Rust FFI 调用

---

## 修改计划

### Phase 1: 实现 Python SDK 的 COW Agent

#### 1.1 创建 CowAgentState 类

```python
# src/runtime/cow_state.py

class CowAgentState:
    """Copy-on-Write Agent 状态管理"""
    
    def __init__(self, parent=None):
        self._parent = parent  # 父状态引用
        self._local_data = {}  # 本地修改
        self._deleted_keys = set()  # 墓碑标记
        self._ref_count = 1
        
    def get(self, key):
        # 优先查找本地修改
        if key in self._deleted_keys:
            return None
        if key in self._local_data:
            return self._local_data[key]
        # 从父状态查找 (COW 链)
        if self._parent:
            return self._parent.get(key)
        return None
    
    def set(self, key, value):
        # 只修改本地数据，不影响父状态
        self._deleted_keys.discard(key)
        self._local_data[key] = value
    
    def clone(self):
        # O(1) 操作 - 只创建新引用
        new_state = CowAgentState(parent=self)
        self._ref_count += 1
        return new_state
    
    def deep_clone(self):
        # O(n) 操作 - 用于对比测试
        new_state = CowAgentState()
        # 需要遍历整个 COW 链获取所有数据
        all_data = self._collect_all_data()
        new_state._local_data = {k: copy.deepcopy(v) for k, v in all_data.items()}
        return new_state
    
    def _collect_all_data(self):
        result = {}
        if self._parent:
            result.update(self._parent._collect_all_data())
        result.update(self._local_data)
        for key in self._deleted_keys:
            result.pop(key, None)
        return result
```

#### 1.2 修改 NexaAgent.clone()

```python
# src/runtime/agent.py

class NexaAgent:
    def __init__(self, ...):
        ...
        self._cow_state = CowAgentState()  # 初始化 COW 状态
        
    def clone(self, new_name: str, **kwargs):
        # 使用 COW 状态克隆 - O(1)
        new_agent = NexaAgent.__new__(NexaAgent)
        new_agent._cow_state = self._cow_state.clone()  # COW 克隆
        new_agent.name = new_name
        # 其他属性覆盖
        ...
        return new_agent
```

### Phase 2: 改进缓存语义匹配

#### 2.1 添加 embedding-based 语义匹配（可选）

```python
# src/runtime/cache_manager.py

class NexaCacheManager:
    def _semantic_similarity(self, text1, text2) -> float:
        """计算语义相似度 (可选使用 embedding)"""
        # 简化版本：使用词汇重叠率
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        overlap = len(words1 & words2)
        return overlap / max(len(words1), len(words2))
    
    def get(self, messages, model, tools=None, use_semantic=True):
        # 精确匹配...
        
        # 语义匹配 - 使用相似度阈值
        if use_semantic and self.enable_semantic_cache:
            last_user_msg = ...
            for cached_key, cached_entry in self._memory_cache.items():
                cached_msg = cached_entry.metadata.get('last_user_msg', '')
                similarity = self._semantic_similarity(last_user_msg, cached_msg)
                if similarity > 0.8:  # 阈值
                    self.stats.record_semantic_hit()
                    return cached_entry.value
```

### Phase 3: 创建真实基准测试

#### 3.1 Python SDK 测试 (使用真实组件)

```python
# tests/test_real_cow_performance.py

import time
import copy
from src.runtime.cow_state import CowAgentState

def test_cow_vs_deep_copy():
    """真实 COW 性能测试"""
    
    # 创建大量数据
    state = CowAgentState()
    for i in range(10000):
        state.set(f"key_{i}", f"value_{i}" * 100)
    
    # COW 克隆测试
    start = time.perf_counter()
    clones = []
    for _ in range(100):
        clones.append(state.clone())
    cow_time = time.perf_counter() - start
    
    # 深拷贝测试
    start = time.perf_counter()
    deep_clones = []
    for _ in range(100):
        deep_clones.append(state.deep_clone())
    deep_time = time.perf_counter() - start
    
    speedup = deep_time / cow_time
    print(f"COW: {cow_time*1000:.2f}ms, Deep: {deep_time*1000:.2f}ms, Speedup: {speedup:.0f}x")
    
    assert speedup > 100  # 至少 100x 加速
```

#### 3.2 缓存命中率测试 (使用真实 NexaCacheManager)

```python
# tests/test_real_cache_hit_rate.py

from src.runtime.cache_manager import NexaCacheManager

def test_cache_hit_rate():
    """真实缓存命中率测试"""
    manager = NexaCacheManager(enable_semantic_cache=True)
    
    # 预热缓存
    for i in range(100):
        messages = [{"role": "user", "content": f"Question {i}: What is {i}?"}]
        manager.set(messages, "gpt-4", f"Answer {i}")
    
    # 测试命中率 - 使用相似问题
    test_queries = [
        [{"role": "user", "content": "Question 0: What is 0?"}],  # 精确匹配
        [{"role": "user", "content": "Question 0: What is zero?"}],  # 语义相似
        [{"role": "user", "content": "Tell me about number 0"}],  # 语义相似
    ]
    
    hits = 0
    for query in test_queries:
        result = manager.get(query, "gpt-4", use_semantic=True)
        if result:
            hits += 1
    
    stats = manager.get_stats()
    print(f"Hit rate: {stats['hit_rate']}")
    
    # 验证命中率
    assert stats['hit_rate'] >= 0.5  # 至少 50% 命中率
```

---

## 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/runtime/cow_state.py` | 新增 | COW 状态管理类 |
| `src/runtime/agent.py` | 修改 | 使用 COW 状态 |
| `src/runtime/cache_manager.py` | 修改 | 改进语义匹配 |
| `tests/test_real_cow_performance.py` | 新增 | 真实 COW 测试 |
| `tests/test_real_cache_hit_rate.py` | 新增 | 真实缓存测试 |
| `tests/test_paper_performance_benchmarks.py` | 删除 | 移除模拟测试 |
| `avm/benches/paper_performance_bench.rs` | 重写 | 使用真实 Rust 组件 |

---

## 验收标准

1. **COW 性能**: Python SDK clone() 达到 >100x 加速比
2. **缓存命中率**: 真实场景达到 >50% 命中率
3. **测试真实性**: 所有测试使用真实运行时组件，无模拟代码
4. **文档准确性**: 论文声明与实际能力一致