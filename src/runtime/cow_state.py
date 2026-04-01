"""
Copy-on-Write (COW) Agent 状态管理

实现 O(1) 时间复杂度的状态分支，支持 Tree-of-Thoughts 模式。
论文声称：COW snapshot 性能提升可达 200,000x (0.1ms vs 20,178ms deep copy)

原理：
- clone() 只创建新引用，不复制数据 - O(1)
- 修改时才创建本地副本 (Copy-on-Write)
- 通过 parent 链实现数据继承
- 墓碑标记 (tombstone) 处理删除操作
"""

import copy
import time
from typing import Any, Dict, Optional, Set, List
from dataclasses import dataclass, field


@dataclass
class CowStats:
    """COW 性能统计"""
    total_clones: int = 0
    total_deep_copies: int = 0
    total_clone_time_ms: float = 0.0
    total_deep_copy_time_ms: float = 0.0
    total_reads: int = 0
    total_writes: int = 0
    
    @property
    def avg_clone_time_ms(self) -> float:
        return self.total_clone_time_ms / self.total_clones if self.total_clones > 0 else 0
    
    @property
    def avg_deep_copy_time_ms(self) -> float:
        return self.total_deep_copy_time_ms / self.total_deep_copies if self.total_deep_copies > 0 else 0
    
    @property
    def speedup(self) -> float:
        if self.total_clone_time_ms > 0 and self.total_deep_copies > 0:
            return self.total_deep_copy_time_ms / self.total_clone_time_ms
        return 0.0
    
    def to_dict(self) -> Dict:
        return {
            "total_clones": self.total_clones,
            "total_deep_copies": self.total_deep_copies,
            "total_clone_time_ms": f"{self.total_clone_time_ms:.3f}",
            "total_deep_copy_time_ms": f"{self.total_deep_copy_time_ms:.3f}",
            "avg_clone_time_ms": f"{self.avg_clone_time_ms:.3f}",
            "avg_deep_copy_time_ms": f"{self.avg_deep_copy_time_ms:.3f}",
            "speedup": f"{self.speedup:.0f}x",
        }


class CowAgentState:
    """
    Copy-on-Write Agent 状态管理
    
    实现原理：
    1. 每个 CowAgentState 可以有父状态 (parent)
    2. clone() 只创建新引用，指向同一 parent - O(1)
    3. 修改时只写入 _local_data，不影响 parent
    4. 读取时遍历 COW 链查找数据
    5. 删除使用墓碑标记 (tombstone)
    
    性能特点：
    - clone(): O(1) 时间复杂度
    - get(): O(d) 时间复杂度，d 为 COW 链深度
    - set(): O(1) 时间复杂度
    - deep_clone(): O(n) 时间复杂度，n 为数据总量
    """
    
    def __init__(self, parent: Optional['CowAgentState'] = None):
        """
        初始化 COW 状态
        
        Args:
            parent: 父状态引用，用于继承数据
        """
        self._parent = parent  # 父状态引用
        self._local_data: Dict[str, Any] = {}  # 本地修改的数据
        self._deleted_keys: Set[str] = set()  # 墓碑标记
        self._ref_count = 1  # 引用计数
        self._created_at = time.time()
        
        # 性能统计
        self._stats = CowStats()
    
    def get(self, key: str) -> Optional[Any]:
        """
        读取值 - 遍历 COW 链查找
        
        Args:
            key: 键名
            
        Returns:
            值，如果不存在返回 None
        """
        self._stats.total_reads += 1
        
        # 检查墓碑
        if key in self._deleted_keys:
            return None
        
        # 查找本地数据
        if key in self._local_data:
            return self._local_data[key]
        
        # 从父状态查找 (COW 链)
        if self._parent:
            return self._parent.get(key)
        
        return None
    
    def set(self, key: str, value: Any) -> None:
        """
        写入值 - 只修改本地数据
        
        Args:
            key: 键名
            value: 值
        """
        self._stats.total_writes += 1
        self._deleted_keys.discard(key)  # 移除墓碑
        self._local_data[key] = value
    
    def delete(self, key: str) -> bool:
        """
        删除值 - 添加墓碑标记
        
        Args:
            key: 键名
            
        Returns:
            是否成功删除
        """
        # 检查键是否存在
        if self.get(key) is not None:
            self._deleted_keys.add(key)
            self._local_data.pop(key, None)
            return True
        return False
    
    def clone(self) -> 'CowAgentState':
        """
        创建 COW 快照 - O(1) 时间复杂度
        
        只创建新引用，不复制数据。
        子状态共享父状态的数据。
        
        Returns:
            新的 COW 状态引用
        """
        start = time.perf_counter()
        
        new_state = CowAgentState(parent=self)
        new_state._stats = self._stats  # 共享统计
        self._ref_count += 1
        
        elapsed = time.perf_counter() - start
        self._stats.total_clones += 1
        self._stats.total_clone_time_ms += elapsed * 1000
        
        return new_state
    
    def deep_clone(self) -> 'CowAgentState':
        """
        创建深拷贝快照 - O(n) 时间复杂度
        
        复制所有数据到新状态，用于性能对比。
        
        Returns:
            完全独立的新状态
        """
        start = time.perf_counter()
        
        # 收集所有数据
        all_data = self._collect_all_data()
        
        # 创建新状态并复制数据
        new_state = CowAgentState()
        new_state._local_data = {k: copy.deepcopy(v) for k, v in all_data.items()}
        
        elapsed = time.perf_counter() - start
        self._stats.total_deep_copies += 1
        self._stats.total_deep_copy_time_ms += elapsed * 1000
        
        return new_state
    
    def create_branch(self) -> 'CowAgentState':
        """
        创建独立分支 - 用于 Tree-of-Thoughts
        
        等同于 clone()，提供语义化命名。
        
        Returns:
            新的分支状态
        """
        return self.clone()
    
    def merge_from(self, source: 'CowAgentState') -> None:
        """
        从源状态合并数据
        
        Args:
            source: 源状态
        """
        source_data = source._collect_all_data()
        for key, value in source_data.items():
            if key not in self._deleted_keys:
                self._local_data[key] = copy.deepcopy(value)
    
    def _collect_all_data(self) -> Dict[str, Any]:
        """
        收集所有数据（包括从 parent 继承的）
        
        Returns:
            包含所有数据的字典
        """
        result = {}
        
        # 先收集父状态数据
        if self._parent:
            result.update(self._parent._collect_all_data())
        
        # 应用本地修改
        result.update(self._local_data)
        
        # 移除已删除的键
        for key in self._deleted_keys:
            result.pop(key, None)
        
        return result
    
    def keys(self) -> List[str]:
        """
        获取所有键
        
        Returns:
            键列表
        """
        all_data = self._collect_all_data()
        return list(all_data.keys())
    
    def values(self) -> List[Any]:
        """
        获取所有值
        
        Returns:
            值列表
        """
        all_data = self._collect_all_data()
        return list(all_data.values())
    
    def items(self) -> List[tuple]:
        """
        获取所有键值对
        
        Returns:
            键值对列表
        """
        all_data = self._collect_all_data()
        return list(all_data.items())
    
    def __contains__(self, key: str) -> bool:
        """支持 'key in state' 语法"""
        return self.get(key) is not None
    
    def __getitem__(self, key: str) -> Any:
        """支持 state[key] 语法"""
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value
    
    def __setitem__(self, key: str, value: Any) -> None:
        """支持 state[key] = value 语法"""
        self.set(key, value)
    
    def __delitem__(self, key: str) -> None:
        """支持 del state[key] 语法"""
        if not self.delete(key):
            raise KeyError(key)
    
    def get_stats(self) -> CowStats:
        """
        获取性能统计
        
        Returns:
            统计信息
        """
        return self._stats
    
    def performance_report(self) -> str:
        """
        生成性能报告
        
        Returns:
            格式化的性能报告字符串
        """
        stats = self.get_stats()
        return f"""COW Agent State Performance Report
====================================
Total Clones: {stats.total_clones}
Total Deep Copies: {stats.total_deep_copies}
Total Clone Time: {stats.total_clone_time_ms:.3f} ms
Total Deep Copy Time: {stats.total_deep_copy_time_ms:.3f} ms
Avg Clone Time: {stats.avg_clone_time_ms:.3f} ms
Avg Deep Copy Time: {stats.avg_deep_copy_time_ms:.3f} ms
Speedup: {stats.speedup:.0f}x

Data Statistics:
  Local Keys: {len(self._local_data)}
  Deleted Keys: {len(self._deleted_keys)}
  Total Keys: {len(self.keys())}
"""


class CowAgentStateRegistry:
    """
    COW 状态注册表
    
    管理多个 COW 状态实例，支持命名查找。
    """
    
    def __init__(self):
        self._states: Dict[str, CowAgentState] = {}
    
    def create(self, name: str) -> CowAgentState:
        """创建新的 COW 状态"""
        state = CowAgentState()
        self._states[name] = state
        return state
    
    def clone(self, source_name: str, target_name: str) -> Optional[CowAgentState]:
        """克隆状态"""
        if source_name not in self._states:
            return None
        new_state = self._states[source_name].clone()
        self._states[target_name] = new_state
        return new_state
    
    def get(self, name: str) -> Optional[CowAgentState]:
        """获取状态"""
        return self._states.get(name)
    
    def delete(self, name: str) -> bool:
        """删除状态"""
        if name in self._states:
            del self._states[name]
            return True
        return False
    
    def list_states(self) -> List[str]:
        """列出所有状态名称"""
        return list(self._states.keys())
    
    def clear(self) -> None:
        """清除所有状态"""
        self._states.clear()


# 全局 COW 状态注册表
_global_registry = CowAgentStateRegistry()


def get_cow_registry() -> CowAgentStateRegistry:
    """获取全局 COW 状态注册表"""
    return _global_registry