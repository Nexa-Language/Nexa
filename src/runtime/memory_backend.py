"""
Nexa 长期记忆后端 (Long-term Memory Backend)
支持大规模的记忆存储和高效的查询，满足agent在复杂任务中的记忆需求
"""

import os
import json
import sqlite3
import hashlib
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod
import threading


class MemoryBackend(ABC):
    """记忆后端抽象基类"""
    
    @abstractmethod
    def store(self, key: str, value: Any, metadata: Dict = None) -> bool:
        """存储记忆"""
        pass
    
    @abstractmethod
    def retrieve(self, key: str) -> Optional[Any]:
        """检索记忆"""
        pass
    
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索记忆"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除记忆"""
        pass
    
    @abstractmethod
    def list_keys(self, prefix: str = None) -> List[str]:
        """列出所有键"""
        pass


class SQLiteMemoryBackend(MemoryBackend):
    """
    SQLite 记忆后端
    
    特性：
    - 本地持久化存储
    - 支持全文搜索 (FTS)
    - 高效的键值检索
    - 支持元数据查询
    """
    
    def __init__(self, db_path: str = ".nexa_memory/memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()
        
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    metadata TEXT,
                    embedding BLOB,
                    created_at REAL,
                    updated_at REAL,
                    access_count INTEGER DEFAULT 0
                );
                
                CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at);
                CREATE INDEX IF NOT EXISTS idx_access_count ON memories(access_count);
                
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    key, value, metadata,
                    content='memories',
                    content_rowid='rowid'
                );
                
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, key, value, metadata)
                    VALUES (new.rowid, new.key, new.value, COALESCE(new.metadata, '{}'));
                END;
                
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, key, value, metadata)
                    VALUES('delete', old.rowid, old.key, old.value, COALESCE(old.metadata, '{}'));
                END;
                
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, key, value, metadata)
                    VALUES('delete', old.rowid, old.key, old.value, COALESCE(old.metadata, '{}'));
                    INSERT INTO memories_fts(rowid, key, value, metadata)
                    VALUES (new.rowid, new.key, new.value, COALESCE(new.metadata, '{}'));
                END;
            ''')
            
    def store(self, key: str, value: Any, metadata: Dict = None) -> bool:
        """存储记忆"""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    now = time.time()
                    value_str = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
                    metadata_str = json.dumps(metadata or {}, ensure_ascii=False)
                    
                    conn.execute('''
                        INSERT OR REPLACE INTO memories (key, value, metadata, created_at, updated_at, access_count)
                        VALUES (?, ?, ?, COALESCE((SELECT created_at FROM memories WHERE key = ?), ?), ?, 
                                COALESCE((SELECT access_count FROM memories WHERE key = ?), 0))
                    ''', (key, value_str, metadata_str, key, now, now, key))
                    
                return True
            except Exception as e:
                print(f"[SQLiteBackend] Store error: {e}")
                return False
                
    def retrieve(self, key: str) -> Optional[Any]:
        """检索记忆"""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute('''
                        UPDATE memories SET access_count = access_count + 1, updated_at = ?
                        WHERE key = ? RETURNING value
                    ''', (time.time(), key))
                    
                    row = cursor.fetchone()
                    if row:
                        try:
                            return json.loads(row['value'])
                        except json.JSONDecodeError:
                            return row['value']
                return None
            except Exception as e:
                print(f"[SQLiteBackend] Retrieve error: {e}")
                return None
                
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """全文搜索"""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute('''
                        SELECT m.key, m.value, m.metadata, m.created_at, m.access_count
                        FROM memories m
                        JOIN memories_fts fts ON m.key = fts.key
                        WHERE memories_fts MATCH ?
                        ORDER BY bm25(memories_fts) DESC, m.access_count DESC
                        LIMIT ?
                    ''', (query, limit))
                    
                    results = []
                    for row in cursor.fetchall():
                        try:
                            value = json.loads(row['value'])
                        except json.JSONDecodeError:
                            value = row['value']
                            
                        results.append({
                            'key': row['key'],
                            'value': value,
                            'metadata': json.loads(row['metadata'] or '{}'),
                            'created_at': row['created_at'],
                            'access_count': row['access_count']
                        })
                        
                    return results
            except Exception as e:
                print(f"[SQLiteBackend] Search error: {e}")
                return []
                
    def delete(self, key: str) -> bool:
        """删除记忆"""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute('DELETE FROM memories WHERE key = ?', (key,))
                return True
            except Exception as e:
                print(f"[SQLiteBackend] Delete error: {e}")
                return False
                
    def list_keys(self, prefix: str = None) -> List[str]:
        """列出所有键"""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    if prefix:
                        cursor = conn.execute(
                            'SELECT key FROM memories WHERE key LIKE ? ORDER BY key',
                            (f'{prefix}%',)
                        )
                    else:
                        cursor = conn.execute('SELECT key FROM memories ORDER BY key')
                        
                    return [row[0] for row in cursor.fetchall()]
            except Exception as e:
                print(f"[SQLiteBackend] List keys error: {e}")
                return []
                
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute('''
                        SELECT 
                            COUNT(*) as total_count,
                            SUM(LENGTH(value)) as total_size,
                            AVG(access_count) as avg_access_count,
                            MAX(created_at) as last_created,
                            MAX(updated_at) as last_updated
                        FROM memories
                    ''')
                    row = cursor.fetchone()
                    return {
                        'total_memories': row[0],
                        'total_size_bytes': row[1] or 0,
                        'avg_access_count': row[2] or 0,
                        'last_created': row[3],
                        'last_updated': row[4]
                    }
            except Exception as e:
                return {'error': str(e)}


class InMemoryBackend(MemoryBackend):
    """内存记忆后端（用于测试和临时存储）"""
    
    def __init__(self):
        self._store: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        
    def store(self, key: str, value: Any, metadata: Dict = None) -> bool:
        with self._lock:
            self._store[key] = {
                'value': value,
                'metadata': metadata or {},
                'created_at': time.time(),
                'access_count': 0
            }
        return True
        
    def retrieve(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry:
                entry['access_count'] += 1
                return entry['value']
        return None
        
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        results = []
        query_lower = query.lower()
        with self._lock:
            for key, entry in self._store.items():
                if (query_lower in key.lower() or 
                    query_lower in str(entry['value']).lower()):
                    results.append({
                        'key': key,
                        'value': entry['value'],
                        'metadata': entry['metadata'],
                        'access_count': entry['access_count']
                    })
        return results[:limit]
        
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
        return False
        
    def list_keys(self, prefix: str = None) -> List[str]:
        with self._lock:
            if prefix:
                return [k for k in self._store.keys() if k.startswith(prefix)]
            return list(self._store.keys())


class VectorMemoryBackend(MemoryBackend):
    """
    向量记忆后端
    
    支持语义相似度搜索，需要向量嵌入支持
    """
    
    def __init__(self, backend: MemoryBackend = None, embedding_dim: int = 384):
        self.backend = backend or SQLiteMemoryBackend()
        self.embedding_dim = embedding_dim
        self._embeddings_cache: Dict[str, List[float]] = {}
        
    def _compute_embedding(self, text: str) -> List[float]:
        """计算文本嵌入（简化实现，实际应使用嵌入模型）"""
        # 使用简单的哈希模拟向量嵌入
        h = hashlib.md5(text.encode()).hexdigest()
        embedding = [float(int(h[i:i+2], 16)) / 255.0 for i in range(0, min(len(h), self.embedding_dim * 2), 2)]
        # 填充到目标维度
        while len(embedding) < self.embedding_dim:
            embedding.extend(embedding[:self.embedding_dim - len(embedding)])
        return embedding[:self.embedding_dim]
        
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
        
    def store(self, key: str, value: Any, metadata: Dict = None) -> bool:
        # 计算并缓存嵌入
        text = f"{key} {json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value}"
        self._embeddings_cache[key] = self._compute_embedding(text)
        return self.backend.store(key, value, metadata)
        
    def retrieve(self, key: str) -> Optional[Any]:
        return self.backend.retrieve(key)
        
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        # 语义搜索
        query_embedding = self._compute_embedding(query)
        
        similarities = []
        for key, embedding in self._embeddings_cache.items():
            sim = self._cosine_similarity(query_embedding, embedding)
            similarities.append((key, sim))
            
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for key, score in similarities[:limit]:
            value = self.backend.retrieve(key)
            if value is not None:
                results.append({
                    'key': key,
                    'value': value,
                    'similarity': score
                })
                
        return results
        
    def delete(self, key: str) -> bool:
        if key in self._embeddings_cache:
            del self._embeddings_cache[key]
        return self.backend.delete(key)
        
    def list_keys(self, prefix: str = None) -> List[str]:
        return self.backend.list_keys(prefix)


class MemoryBackendManager:
    """
    记忆后端管理器
    
    管理多个记忆后端，支持分层存储
    """
    
    def __init__(self, default_backend: MemoryBackend = None):
        self.backends: Dict[str, MemoryBackend] = {}
        self.default_backend = default_backend or SQLiteMemoryBackend()
        
    def register_backend(self, name: str, backend: MemoryBackend):
        """注册后端"""
        self.backends[name] = backend
        
    def get_backend(self, name: str = None) -> MemoryBackend:
        """获取后端"""
        if name and name in self.backends:
            return self.backends[name]
        return self.default_backend
        
    def store(self, key: str, value: Any, backend_name: str = None, metadata: Dict = None) -> bool:
        """存储到指定后端"""
        backend = self.get_backend(backend_name)
        return backend.store(key, value, metadata)
        
    def retrieve(self, key: str, backend_name: str = None) -> Optional[Any]:
        """从指定后端检索"""
        backend = self.get_backend(backend_name)
        return backend.retrieve(key)
        
    def search_all(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索所有后端"""
        results = []
        for name, backend in self.backends.items():
            backend_results = backend.search(query, limit)
            for r in backend_results:
                r['backend'] = name
            results.extend(backend_results)
        return sorted(results, key=lambda x: x.get('similarity', 0) or x.get('access_count', 0), reverse=True)[:limit]


# 全局后端管理器
_global_backend_manager: Optional[MemoryBackendManager] = None


def get_backend_manager() -> MemoryBackendManager:
    """获取全局后端管理器"""
    global _global_backend_manager
    if _global_backend_manager is None:
        _global_backend_manager = MemoryBackendManager()
    return _global_backend_manager


def get_memory_backend(name: str = None) -> MemoryBackend:
    """获取记忆后端"""
    return get_backend_manager().get_backend(name)


__all__ = [
    'MemoryBackend', 'SQLiteMemoryBackend', 'InMemoryBackend', 'VectorMemoryBackend',
    'MemoryBackendManager', 'get_backend_manager', 'get_memory_backend'
]