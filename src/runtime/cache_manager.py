"""
Nexa 智能缓存管理器 - 编程语言层面的缓存机制
支持语义缓存、多级缓存、缓存过期策略、缓存统计等高级功能
"""

import os
import json
import hashlib
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
from pathlib import Path


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    expires_at: Optional[float] = None
    hit_count: int = 0
    semantic_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def touch(self):
        """增加命中计数"""
        self.hit_count += 1


class CacheStats:
    """缓存统计"""
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.semantic_hits = 0
        self.total_size_bytes = 0
        
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def record_hit(self):
        self.hits += 1
        
    def record_miss(self):
        self.misses += 1
        
    def record_semantic_hit(self):
        self.semantic_hits += 1
        self.hits += 1
        
    def record_eviction(self):
        self.evictions += 1
        
    def to_dict(self) -> Dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.2%}",
            "semantic_hits": self.semantic_hits,
            "evictions": self.evictions,
            "total_size_bytes": self.total_size_bytes
        }


class NexaCacheManager:
    """
    Nexa 智能缓存管理器
    
    特性：
    - 多级缓存：内存缓存 (L1) + 磁盘缓存 (L2)
    - 语义缓存：基于输入相似度的智能匹配
    - TTL支持：可配置的缓存过期时间
    - 缓存统计：命中率、驱逐次数等
    - 线程安全：支持并发访问
    """
    
    DEFAULT_CACHE_DIR = ".nexa_cache"
    DEFAULT_TTL = 3600 * 24  # 24小时
    MAX_MEMORY_ENTRIES = 1000
    MAX_DISK_SIZE_MB = 100
    
    def __init__(
        self,
        cache_dir: str = None,
        default_ttl: int = None,
        enable_semantic_cache: bool = True,
        enable_disk_cache: bool = True
    ):
        self.cache_dir = Path(cache_dir or self.DEFAULT_CACHE_DIR)
        self.default_ttl = default_ttl or self.DEFAULT_TTL
        self.enable_semantic_cache = enable_semantic_cache
        self.enable_disk_cache = enable_disk_cache
        
        # 内存缓存 (L1)
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        
        # 缓存统计
        self.stats = CacheStats()
        
        # 语义缓存索引 (简化版：基于关键词)
        self._semantic_index: Dict[str, List[str]] = {}
        
        # 初始化
        if self.enable_disk_cache:
            self._init_disk_cache()
            
    def _init_disk_cache(self):
        """初始化磁盘缓存目录"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._disk_cache_file = self.cache_dir / "llm_cache.json"
        self._load_disk_cache()
        
    def _load_disk_cache(self):
        """从磁盘加载缓存"""
        if not self._disk_cache_file.exists():
            return
            
        try:
            with open(self._disk_cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            current_time = time.time()
            for key, entry_data in data.items():
                # 跳过过期条目
                if entry_data.get("expires_at") and entry_data["expires_at"] < current_time:
                    continue
                    
                entry = CacheEntry(
                    key=key,
                    value=entry_data["value"],
                    created_at=entry_data["created_at"],
                    expires_at=entry_data.get("expires_at"),
                    hit_count=entry_data.get("hit_count", 0),
                    semantic_hash=entry_data.get("semantic_hash"),
                    metadata=entry_data.get("metadata", {})
                )
                self._memory_cache[key] = entry
                
        except Exception as e:
            print(f"[CacheManager] Warning: Failed to load disk cache: {e}")
            
    def _save_disk_cache(self):
        """保存缓存到磁盘"""
        if not self.enable_disk_cache:
            return
            
        try:
            data = {}
            for key, entry in self._memory_cache.items():
                if not entry.is_expired():
                    data[key] = {
                        "value": entry.value,
                        "created_at": entry.created_at,
                        "expires_at": entry.expires_at,
                        "hit_count": entry.hit_count,
                        "semantic_hash": entry.semantic_hash,
                        "metadata": entry.metadata
                    }
                    
            with open(self._disk_cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"[CacheManager] Warning: Failed to save disk cache: {e}")
            
    def _generate_key(self, messages: List[Dict], model: str, tools: List = None) -> str:
        """生成缓存键"""
        cache_data = {
            "messages": messages,
            "model": model
        }
        if tools:
            cache_data["tools"] = [str(t) for t in tools]
            
        data_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode("utf-8")).hexdigest()
    
    def _generate_semantic_hash(self, text: str) -> str:
        """
        生成语义哈希（简化版）
        基于关键词提取，用于语义缓存匹配
        """
        # 简化版：提取关键词并排序
        words = text.lower().split()
        # 过滤常见停用词
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", 
                      "being", "have", "has", "had", "do", "does", "did", "will",
                      "would", "could", "should", "may", "might", "must", "shall",
                      "can", "need", "dare", "ought", "used", "to", "of", "in",
                      "for", "on", "with", "at", "by", "from", "as", "into",
                      "through", "during", "before", "after", "above", "below",
                      "between", "under", "again", "further", "then", "once"}
        
        keywords = sorted(set(w for w in words if w not in stop_words and len(w) > 2))
        return hashlib.md5(" ".join(keywords).encode()).hexdigest()
    
    def get(
        self,
        messages: List[Dict],
        model: str,
        tools: List = None,
        use_semantic: bool = True
    ) -> Optional[str]:
        """
        从缓存获取结果
        
        Args:
            messages: 对话消息列表
            model: 模型名称
            tools: 工具列表
            use_semantic: 是否使用语义缓存
            
        Returns:
            缓存的结果，如果未命中返回None
        """
        with self._lock:
            key = self._generate_key(messages, model, tools)
            
            # 精确匹配
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                if not entry.is_expired():
                    entry.touch()
                    self.stats.record_hit()
                    print(f"[CacheManager] ✓ Cache HIT (exact): {key[:8]}...")
                    return entry.value
                else:
                    # 清理过期条目
                    del self._memory_cache[key]
                    self.stats.record_eviction()
                    
            # 语义匹配
            if use_semantic and self.enable_semantic_cache:
                # 获取最后一条用户消息
                last_user_msg = ""
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        last_user_msg = msg.get("content", "")
                        break
                        
                if last_user_msg:
                    semantic_hash = self._generate_semantic_hash(last_user_msg)
                    
                    # 在语义索引中查找相似查询
                    if semantic_hash in self._semantic_index:
                        for similar_key in self._semantic_index[semantic_hash]:
                            if similar_key in self._memory_cache:
                                entry = self._memory_cache[similar_key]
                                if not entry.is_expired():
                                    entry.touch()
                                    self.stats.record_semantic_hit()
                                    print(f"[CacheManager] ✓ Cache HIT (semantic): {similar_key[:8]}...")
                                    return entry.value
                                    
            self.stats.record_miss()
            print(f"[CacheManager] ✗ Cache MISS: {key[:8]}...")
            return None
            
    def set(
        self,
        messages: List[Dict],
        model: str,
        result: str,
        tools: List = None,
        ttl: int = None,
        metadata: Dict = None
    ):
        """
        设置缓存
        
        Args:
            messages: 对话消息列表
            model: 模型名称
            result: 缓存结果
            tools: 工具列表
            ttl: 过期时间（秒）
            metadata: 元数据
        """
        with self._lock:
            key = self._generate_key(messages, model, tools)
            current_time = time.time()
            expires_at = current_time + (ttl or self.default_ttl) if ttl != -1 else None
            
            # 生成语义哈希
            semantic_hash = None
            if self.enable_semantic_cache:
                last_user_msg = ""
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        last_user_msg = msg.get("content", "")
                        break
                if last_user_msg:
                    semantic_hash = self._generate_semantic_hash(last_user_msg)
                    # 更新语义索引
                    if semantic_hash not in self._semantic_index:
                        self._semantic_index[semantic_hash] = []
                    if key not in self._semantic_index[semantic_hash]:
                        self._semantic_index[semantic_hash].append(key)
            
            entry = CacheEntry(
                key=key,
                value=result,
                created_at=current_time,
                expires_at=expires_at,
                semantic_hash=semantic_hash,
                metadata=metadata or {}
            )
            
            self._memory_cache[key] = entry
            
            # 内存缓存大小管理
            if len(self._memory_cache) > self.MAX_MEMORY_ENTRIES:
                self._evict_lru()
                
            # 异步保存到磁盘
            self._save_disk_cache()
            
            print(f"[CacheManager] ✓ Cache SET: {key[:8]}... (TTL: {ttl or self.default_ttl}s)")
            
    def _evict_lru(self):
        """LRU驱逐策略"""
        if not self._memory_cache:
            return
            
        # 按访问次数和创建时间排序
        sorted_entries = sorted(
            self._memory_cache.items(),
            key=lambda x: (x[1].hit_count, x[1].created_at)
        )
        
        # 驱逐10%的条目
        evict_count = max(1, len(sorted_entries) // 10)
        for key, _ in sorted_entries[:evict_count]:
            del self._memory_cache[key]
            self.stats.record_eviction()
            
        print(f"[CacheManager] Evicted {evict_count} LRU entries")
        
    def invalidate(self, pattern: str = None):
        """
        使缓存失效
        
        Args:
            pattern: 键模式（支持前缀匹配），None表示清空所有
        """
        with self._lock:
            if pattern is None:
                count = len(self._memory_cache)
                self._memory_cache.clear()
                self._semantic_index.clear()
                self.stats.record_eviction()
                print(f"[CacheManager] Invalidated ALL ({count} entries)")
            else:
                keys_to_remove = [k for k in self._memory_cache if k.startswith(pattern)]
                for key in keys_to_remove:
                    del self._memory_cache[key]
                    self.stats.record_eviction()
                print(f"[CacheManager] Invalidated {len(keys_to_remove)} entries matching '{pattern}'")
                
            self._save_disk_cache()
            
    def get_stats(self) -> Dict:
        """获取缓存统计信息"""
        return {
            **self.stats.to_dict(),
            "memory_entries": len(self._memory_cache),
            "semantic_index_size": len(self._semantic_index),
            "config": {
                "default_ttl": self.default_ttl,
                "max_memory_entries": self.MAX_MEMORY_ENTRIES,
                "semantic_cache_enabled": self.enable_semantic_cache,
                "disk_cache_enabled": self.enable_disk_cache
            }
        }
        
    def warmup(self, entries: List[Tuple[List[Dict], str, str]]):
        """
        缓存预热
        
        Args:
            entries: [(messages, model, result), ...] 预热数据列表
        """
        print(f"[CacheManager] Warming up cache with {len(entries)} entries...")
        for messages, model, result in entries:
            self.set(messages, model, result)
        print(f"[CacheManager] Cache warmup complete")


# 全局缓存管理器实例
_global_cache_manager: Optional[NexaCacheManager] = None


def get_cache_manager() -> NexaCacheManager:
    """获取全局缓存管理器实例"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = NexaCacheManager()
    return _global_cache_manager


def init_cache_manager(**kwargs) -> NexaCacheManager:
    """初始化全局缓存管理器"""
    global _global_cache_manager
    _global_cache_manager = NexaCacheManager(**kwargs)
    return _global_cache_manager


# 便捷函数
def cache_get(messages: List[Dict], model: str, tools: List = None) -> Optional[str]:
    """便捷缓存获取函数"""
    return get_cache_manager().get(messages, model, tools)


def cache_set(messages: List[Dict], model: str, result: str, tools: List = None, ttl: int = None):
    """便捷缓存设置函数"""
    get_cache_manager().set(messages, model, result, tools, ttl)


__all__ = [
    'NexaCacheManager', 'CacheEntry', 'CacheStats',
    'get_cache_manager', 'init_cache_manager',
    'cache_get', 'cache_set'
]