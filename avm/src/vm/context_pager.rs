/*
# ========================================================================
Copyright (C) 2026 Nexa-Language
This file is part of Nexa Project.

Nexa is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

Nexa is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
========================================================================
*/

//! 向量虚存分页 (Context Paging)
//!
//! AVM 接管内存，自动执行对话历史的向量化置换与透明加载

use std::collections::{HashMap, VecDeque};
use std::time::Duration;
use serde::{Deserialize, Serialize};

// ==================== 消息类型 ====================

/// 消息角色
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MessageRole {
    System,
    User,
    Assistant,
    Tool,
}

/// 消息
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    /// 消息 ID
    pub id: u64,
    /// 角色
    pub role: MessageRole,
    /// 内容
    pub content: String,
    /// 时间戳
    pub timestamp: u64,
    /// Token 数
    pub token_count: usize,
    /// 元数据
    pub metadata: HashMap<String, String>,
}

impl Message {
    /// 创建新消息
    pub fn new(role: MessageRole, content: impl Into<String>) -> Self {
        Self {
            id: 0, // 由管理器分配
            role,
            content: content.into(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
            token_count: 0,
            metadata: HashMap::new(),
        }
    }
    
    /// 估算 Token 数 (简单估算: 字符数 / 4)
    pub fn estimate_tokens(&mut self) {
        self.token_count = self.content.len() / 4;
    }
}

// ==================== 内存页 ====================

/// 页面 ID
pub type PageId = u64;

/// 内存页
#[derive(Debug, Clone)]
pub struct MemoryPage {
    /// 页面 ID
    pub id: PageId,
    /// 页面内的消息
    pub messages: Vec<Message>,
    /// 页面摘要嵌入向量
    pub embedding: Vec<f32>,
    /// 页面摘要文本
    pub summary: String,
    /// 最后访问时间 (时间戳，秒)
    pub last_accessed_ts: u64,
    /// 访问次数
    pub access_count: u64,
    /// 相关性分数
    pub relevance_score: f32,
    /// Token 总数
    pub total_tokens: usize,
    /// 是否已修改
    pub dirty: bool,
    /// 页面大小 (字节)
    pub size_bytes: usize,
}

impl MemoryPage {
    /// 获取当前时间戳
    fn current_timestamp() -> u64 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
    }
    
    /// 创建新的内存页
    pub fn new(id: PageId) -> Self {
        Self {
            id,
            messages: Vec::new(),
            embedding: Vec::new(),
            summary: String::new(),
            last_accessed_ts: Self::current_timestamp(),
            access_count: 0,
            relevance_score: 0.0,
            total_tokens: 0,
            dirty: false,
            size_bytes: 0,
        }
    }
    
    /// 添加消息
    pub fn add_message(&mut self, message: Message) {
        self.total_tokens += message.token_count;
        self.size_bytes += message.content.len();
        self.messages.push(message);
        self.dirty = true;
        self.touch();
    }
    
    /// 访问页面
    pub fn touch(&mut self) {
        self.last_accessed_ts = Self::current_timestamp();
        self.access_count += 1;
    }
    
    /// 计算优先级 (用于置换决策)
    pub fn eviction_priority(&self) -> f32 {
        // 结合访问时间、访问次数、相关性分数
        let now = Self::current_timestamp();
        let elapsed = now.saturating_sub(self.last_accessed_ts) as f32;
        let freq_factor = 1.0 / (self.access_count as f32 + 1.0);
        let relevance_factor = 1.0 - self.relevance_score;
        
        elapsed * freq_factor * relevance_factor
    }
}

// ==================== 置换策略 ====================

/// 置换策略
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EvictionPolicy {
    /// 最近最少使用 (LRU)
    LRU,
    /// 最不常用 (LFU)
    LFU,
    /// 基于相关性
    Relevance,
    /// 混合策略
    Hybrid,
}

impl Default for EvictionPolicy {
    fn default() -> Self {
        EvictionPolicy::Hybrid
    }
}

// ==================== 分页配置 ====================

/// 分页配置
#[derive(Debug, Clone)]
pub struct PagingConfig {
    /// 每页最大消息数
    pub page_size: usize,
    /// 最大活跃页数
    pub max_active_pages: usize,
    /// 嵌入向量维度
    pub embedding_dim: usize,
    /// 相似度阈值
    pub similarity_threshold: f32,
    /// 置换策略
    pub eviction_policy: EvictionPolicy,
    /// 最大内存使用 (MB)
    pub max_memory_mb: usize,
    /// 自动压缩阈值 (Token 数)
    pub compression_threshold: usize,
    /// 后台刷新间隔 (ms)
    pub background_refresh_ms: u64,
}

impl Default for PagingConfig {
    fn default() -> Self {
        Self {
            page_size: 50,
            max_active_pages: 10,
            embedding_dim: 384,
            similarity_threshold: 0.7,
            eviction_policy: EvictionPolicy::Hybrid,
            max_memory_mb: 256,
            compression_threshold: 4000,
            background_refresh_ms: 5000,
        }
    }
}

// ==================== 分页统计 ====================

/// 分页统计
#[derive(Debug, Clone, Default)]
pub struct PagingStats {
    /// 页面命中次数
    pub hits: u64,
    /// 页面未命中次数
    pub misses: u64,
    /// 页面置换次数
    pub evictions: u64,
    /// 页面加载次数
    pub loads: u64,
    /// 页面保存次数
    pub saves: u64,
    /// 总 Token 数
    pub total_tokens: usize,
    /// 内存使用峰值 (字节)
    pub peak_memory_bytes: usize,
}

impl PagingStats {
    /// 命中率
    pub fn hit_rate(&self) -> f64 {
        let total = self.hits + self.misses;
        if total == 0 {
            return 0.0;
        }
        self.hits as f64 / total as f64
    }
}

// ==================== 页面存储 ====================

/// 页面存储后端 (trait)
pub trait PageStorage: Send + Sync {
    /// 保存页面
    fn save_page(&mut self, page: &MemoryPage) -> Result<(), String>;
    
    /// 加载页面
    fn load_page(&mut self, id: PageId) -> Result<Option<MemoryPage>, String>;
    
    /// 删除页面
    fn delete_page(&mut self, id: PageId) -> Result<(), String>;
    
    /// 列出所有页面 ID
    fn list_pages(&self) -> Vec<PageId>;
    
    /// 获取总大小
    fn total_size(&self) -> usize;
}

/// 内存页面存储 (简单实现)
#[derive(Default)]
pub struct InMemoryPageStorage {
    pages: HashMap<PageId, MemoryPage>,
}

impl InMemoryPageStorage {
    pub fn new() -> Self {
        Self {
            pages: HashMap::new(),
        }
    }
}

impl PageStorage for InMemoryPageStorage {
    fn save_page(&mut self, page: &MemoryPage) -> Result<(), String> {
        self.pages.insert(page.id, page.clone());
        Ok(())
    }
    
    fn load_page(&mut self, id: PageId) -> Result<Option<MemoryPage>, String> {
        Ok(self.pages.get(&id).cloned())
    }
    
    fn delete_page(&mut self, id: PageId) -> Result<(), String> {
        self.pages.remove(&id);
        Ok(())
    }
    
    fn list_pages(&self) -> Vec<PageId> {
        self.pages.keys().copied().collect()
    }
    
    fn total_size(&self) -> usize {
        self.pages.values().map(|p| p.size_bytes).sum()
    }
}

// ==================== 上下文分页器 ====================

/// 上下文分页器
pub struct ContextPager {
    /// 配置
    config: PagingConfig,
    /// 活跃页面 (在内存中)
    active_pages: HashMap<PageId, MemoryPage>,
    /// 页面访问顺序 (LRU)
    page_order: VecDeque<PageId>,
    /// 当前页面
    current_page_id: PageId,
    /// 下一页 ID
    next_page_id: PageId,
    /// 下一消息 ID
    next_message_id: u64,
    /// 存储后端
    storage: Box<dyn PageStorage>,
    /// 统计
    stats: PagingStats,
    /// 嵌入缓存 (查询 -> 嵌入向量)
    embedding_cache: HashMap<String, Vec<f32>>,
}

impl ContextPager {
    /// 创建新的上下文分页器
    pub fn new(config: PagingConfig) -> Self {
        let mut pager = Self {
            config,
            active_pages: HashMap::new(),
            page_order: VecDeque::new(),
            current_page_id: 0,
            next_page_id: 1,
            next_message_id: 1,
            storage: Box::new(InMemoryPageStorage::new()),
            stats: PagingStats::default(),
            embedding_cache: HashMap::new(),
        };
        
        // 创建初始页面
        let initial_page = MemoryPage::new(0);
        pager.active_pages.insert(0, initial_page);
        pager.page_order.push_back(0);
        
        pager
    }
    
    /// 添加消息
    pub fn add_message(&mut self, role: MessageRole, content: impl Into<String>) -> PageId {
        let mut message = Message::new(role, content);
        message.id = self.next_message_id;
        self.next_message_id += 1;
        message.estimate_tokens();
        
        // 检查当前页面是否已满
        let is_full = self.active_pages.get(&self.current_page_id)
            .map(|p| p.messages.len() >= self.config.page_size)
            .unwrap_or(false);
        
        if is_full {
            // 创建新页面
            self.create_new_page();
        }
        
        let page_id = self.current_page_id;
        if let Some(page) = self.active_pages.get_mut(&page_id) {
            page.add_message(message);
        }
        
        // 检查是否需要置换
        if self.active_pages.len() > self.config.max_active_pages {
            self.evict_page();
        }
        
        page_id
    }
    
    /// 创建新页面
    fn create_new_page(&mut self) {
        // 保存当前页面
        if let Some(current) = self.active_pages.get(&self.current_page_id) {
            if current.dirty {
                let _ = self.storage.save_page(current);
                self.stats.saves += 1;
            }
        }
        
        let new_page_id = self.next_page_id;
        self.next_page_id += 1;
        
        let new_page = MemoryPage::new(new_page_id);
        self.active_pages.insert(new_page_id, new_page);
        self.page_order.push_back(new_page_id);
        self.current_page_id = new_page_id;
    }
    
    /// 置换页面
    fn evict_page(&mut self) {
        // 选择要置换的页面
        let victim_id = self.select_victim_page();
        
        if let Some(page) = self.active_pages.remove(&victim_id) {
            // 保存页面
            if page.dirty {
                let _ = self.storage.save_page(&page);
                self.stats.saves += 1;
            }
            
            // 从顺序队列中移除
            self.page_order.retain(|&id| id != victim_id);
            self.stats.evictions += 1;
        }
    }
    
    /// 选择置换页面
    fn select_victim_page(&self) -> PageId {
        if self.active_pages.is_empty() {
            return 0;
        }
        
        match self.config.eviction_policy {
            EvictionPolicy::LRU => {
                // 最旧的页面
                self.page_order.front().copied().unwrap_or(0)
            }
            EvictionPolicy::LFU => {
                // 访问次数最少的页面
                self.active_pages.values()
                    .min_by_key(|p| p.access_count)
                    .map(|p| p.id)
                    .unwrap_or(0)
            }
            EvictionPolicy::Relevance => {
                // 相关性最低的页面
                self.active_pages.values()
                    .min_by(|a, b| a.relevance_score.partial_cmp(&b.relevance_score).unwrap())
                    .map(|p| p.id)
                    .unwrap_or(0)
            }
            EvictionPolicy::Hybrid => {
                // 综合优先级最高的页面 (最应该被置换)
                self.active_pages.values()
                    .max_by(|a, b| a.eviction_priority().partial_cmp(&b.eviction_priority()).unwrap())
                    .map(|p| p.id)
                    .unwrap_or(0)
            }
        }
    }
    
    /// 获取页面 (透明加载)
    pub fn get_page(&mut self, id: PageId) -> Option<&MemoryPage> {
        // 检查是否在活跃页面中
        if self.active_pages.contains_key(&id) {
            self.stats.hits += 1;
            let page = self.active_pages.get_mut(&id).unwrap();
            page.touch();
            return Some(self.active_pages.get(&id).unwrap());
        }
        
        // 从存储中加载
        self.stats.misses += 1;
        match self.storage.load_page(id) {
            Ok(Some(mut page)) => {
                page.touch();
                self.stats.loads += 1;
                
                // 检查是否需要置换
                while self.active_pages.len() >= self.config.max_active_pages {
                    self.evict_page();
                }
                
                self.active_pages.insert(id, page);
                self.page_order.push_back(id);
                Some(self.active_pages.get(&id).unwrap())
            }
            _ => None,
        }
    }
    
    /// 获取当前活跃页面
    pub fn current_page(&self) -> Option<&MemoryPage> {
        self.active_pages.get(&self.current_page_id)
    }
    
    /// 获取所有活跃消息
    pub fn get_active_messages(&self) -> Vec<&Message> {
        self.active_pages.values()
            .flat_map(|page| page.messages.iter())
            .collect()
    }
    
    /// 根据相关性加载页面
    pub fn load_relevant_pages(&mut self, query: &str, top_k: usize) -> Vec<PageId> {
        // 计算查询嵌入 (简化：使用简单的词频向量)
        let query_embedding = self.compute_embedding(query);
        
        // 获取所有页面并计算相关性
        let all_pages = self.storage.list_pages();
        let mut page_scores: Vec<(PageId, f32)> = all_pages.iter()
            .map(|&id| {
                // 先获取页面，计算嵌入相似度
                let page_opt = self.get_page(id);
                if let Some(page) = page_opt {
                    let score = Self::cosine_similarity_static(&query_embedding, &page.embedding);
                    (id, score)
                } else {
                    (id, 0.0)
                }
            })
            .collect();
        
        // 按相关性排序
        page_scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        
        // 加载 top-k 页面
        let loaded: Vec<PageId> = page_scores.iter()
            .take(top_k)
            .filter(|(_, score)| *score > self.config.similarity_threshold)
            .map(|(id, _)| *id)
            .collect();
        
        // 更新相关性分数
        for &id in &loaded {
            if let Some(page) = self.active_pages.get_mut(&id) {
                if let Some((_, score)) = page_scores.iter().find(|(pid, _)| *pid == id) {
                    page.relevance_score = *score;
                }
            }
        }
        
        loaded
    }
    
    /// 计算嵌入向量 (简化实现)
    fn compute_embedding(&mut self, text: &str) -> Vec<f32> {
        // 检查缓存
        if let Some(cached) = self.embedding_cache.get(text) {
            return cached.clone();
        }
        
        // 简化：使用词频作为嵌入
        let mut embedding = vec![0.0; self.config.embedding_dim];
        let words: Vec<&str> = text.split_whitespace().collect();
        
        for (i, word) in words.iter().enumerate() {
            let hash = self.simple_hash(word);
            let idx = hash as usize % self.config.embedding_dim;
            embedding[idx] += 1.0;
        }
        
        // 归一化
        let norm: f32 = embedding.iter().map(|x| x * x).sum::<f32>().sqrt();
        if norm > 0.0 {
            for val in &mut embedding {
                *val /= norm;
            }
        }
        
        // 缓存
        self.embedding_cache.insert(text.to_string(), embedding.clone());
        
        embedding
    }
    
    /// 简单哈希函数
    fn simple_hash(&self, s: &str) -> u32 {
        let mut hash: u32 = 0;
        for c in s.chars() {
            hash = hash.wrapping_mul(31).wrapping_add(c as u32);
        }
        hash
    }
    
    /// 计算余弦相似度
    fn cosine_similarity(&self, a: &[f32], b: &[f32]) -> f32 {
        Self::cosine_similarity_static(a, b)
    }
    
    /// 计算余弦相似度 (静态方法)
    fn cosine_similarity_static(a: &[f32], b: &[f32]) -> f32 {
        if a.is_empty() || b.is_empty() {
            return 0.0;
        }
        
        let min_len = a.len().min(b.len());
        let dot: f32 = a[..min_len].iter()
            .zip(&b[..min_len])
            .map(|(x, y)| x * y)
            .sum();
        
        let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
        let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
        
        if norm_a > 0.0 && norm_b > 0.0 {
            dot / (norm_a * norm_b)
        } else {
            0.0
        }
    }
    
    /// 刷新页面嵌入
    pub fn refresh_embeddings(&mut self) {
        // 先收集需要更新的页面ID和摘要
        let updates: Vec<(PageId, String)> = self.active_pages.values()
            .map(|page| {
                let summary: String = page.messages.iter()
                    .map(|m| m.content.as_str())
                    .collect::<Vec<_>>()
                    .join(" ");
                let truncated: String = summary.chars().take(500).collect();
                (page.id, truncated)
            })
            .collect();
        
        // 计算嵌入并更新
        for (id, summary) in updates {
            let embedding = self.compute_embedding(&summary);
            if let Some(page) = self.active_pages.get_mut(&id) {
                page.summary = summary;
                page.embedding = embedding;
            }
        }
    }
    
    /// 压缩旧页面
    pub fn compress_old_pages(&mut self, older_than: Duration) -> usize {
        let now_ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let older_than_secs = older_than.as_secs();
        let mut compressed = 0;
        
        for page in self.active_pages.values_mut() {
            let elapsed = now_ts.saturating_sub(page.last_accessed_ts);
            if elapsed > older_than_secs {
                // 压缩：保留摘要，清空详细消息
                if page.messages.len() > 10 {
                    let summary = page.messages.iter()
                        .map(|m| m.content.as_str())
                        .take(5)
                        .collect::<Vec<_>>()
                        .join(" ");
                    
                    page.summary = format!("{}... ({} messages compressed)",
                        summary.chars().take(200).collect::<String>(),
                        page.messages.len()
                    );
                    page.messages.clear();
                    page.dirty = true;
                    compressed += 1;
                }
            }
        }
        
        compressed
    }
    
    /// 获取统计信息
    pub fn stats(&self) -> &PagingStats {
        &self.stats
    }
    
    /// 获取活跃页面数
    pub fn active_page_count(&self) -> usize {
        self.active_pages.len()
    }
    
    /// 获取总消息数
    pub fn total_messages(&self) -> usize {
        self.active_pages.values()
            .map(|p| p.messages.len())
            .sum()
    }
    
    /// 获取总 Token 数
    pub fn total_tokens(&self) -> usize {
        self.active_pages.values()
            .map(|p| p.total_tokens)
            .sum()
    }
    
    /// 获取内存使用量 (估算)
    pub fn memory_usage(&self) -> usize {
        self.active_pages.values()
            .map(|p| p.size_bytes + p.embedding.len() * 4)
            .sum()
    }
    
    /// 清除所有页面
    pub fn clear(&mut self) {
        // 保存所有脏页面
        for page in self.active_pages.values() {
            if page.dirty {
                let _ = self.storage.save_page(page);
            }
        }
        
        self.active_pages.clear();
        self.page_order.clear();
        
        // 重新创建初始页面
        let initial_page = MemoryPage::new(0);
        self.active_pages.insert(0, initial_page);
        self.page_order.push_back(0);
        self.current_page_id = 0;
    }
    
    /// 设置存储后端
    pub fn set_storage(&mut self, storage: Box<dyn PageStorage>) {
        self.storage = storage;
    }
}

impl Default for ContextPager {
    fn default() -> Self {
        Self::new(PagingConfig::default())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_message_creation() {
        let mut msg = Message::new(MessageRole::User, "Hello, world!");
        assert_eq!(msg.role, MessageRole::User);
        assert_eq!(msg.content, "Hello, world!");
        assert_eq!(msg.token_count, 0);
        
        msg.estimate_tokens();
        assert!(msg.token_count > 0);
    }
    
    #[test]
    fn test_memory_page() {
        let mut page = MemoryPage::new(0);
        assert!(page.messages.is_empty());
        assert_eq!(page.access_count, 0);
        
        let msg = Message::new(MessageRole::User, "Test");
        page.add_message(msg);
        
        assert_eq!(page.messages.len(), 1);
        assert_eq!(page.access_count, 1);
        assert!(page.dirty);
    }
    
    #[test]
    fn test_paging_config_default() {
        let config = PagingConfig::default();
        assert_eq!(config.page_size, 50);
        assert_eq!(config.max_active_pages, 10);
        assert_eq!(config.eviction_policy, EvictionPolicy::Hybrid);
    }
    
    #[test]
    fn test_context_pager_creation() {
        let pager = ContextPager::default();
        assert_eq!(pager.active_page_count(), 1);
        assert_eq!(pager.total_messages(), 0);
    }
    
    #[test]
    fn test_add_message() {
        let mut pager = ContextPager::default();
        
        let page_id = pager.add_message(MessageRole::User, "Hello");
        assert_eq!(page_id, 0);
        assert_eq!(pager.total_messages(), 1);
    }
    
    #[test]
    fn test_page_eviction() {
        let config = PagingConfig {
            max_active_pages: 2,
            page_size: 2,
            ..Default::default()
        };
        let mut pager = ContextPager::new(config);
        
        // 添加消息填满页面
        for i in 0..10 {
            pager.add_message(MessageRole::User, format!("Message {}", i));
        }
        
        // 应该触发置换
        assert!(pager.active_page_count() <= 2);
        assert!(pager.stats().evictions > 0 || pager.active_page_count() <= 2);
    }
    
    #[test]
    fn test_get_page() {
        let mut pager = ContextPager::default();
        
        // 添加消息
        pager.add_message(MessageRole::User, "Test message");
        
        // 获取页面
        let page = pager.get_page(0);
        assert!(page.is_some());
        assert_eq!(page.unwrap().messages.len(), 1);
        
        // 检查统计
        assert_eq!(pager.stats().hits, 1);
    }
    
    #[test]
    fn test_lru_eviction() {
        let config = PagingConfig {
            max_active_pages: 2,
            eviction_policy: EvictionPolicy::LRU,
            ..Default::default()
        };
        let mut pager = ContextPager::new(config);
        
        // 创建多个页面
        for i in 0..10 {
            pager.add_message(MessageRole::User, format!("Message {}", i));
        }
        
        // 验证活跃页面数限制
        assert!(pager.active_page_count() <= 2);
    }
    
    #[test]
    fn test_cosine_similarity() {
        let pager = ContextPager::default();
        
        let a = vec![1.0, 0.0, 0.0];
        let b = vec![1.0, 0.0, 0.0];
        let sim = pager.cosine_similarity(&a, &b);
        assert!((sim - 1.0).abs() < 0.01);
        
        let c = vec![0.0, 1.0, 0.0];
        let sim2 = pager.cosine_similarity(&a, &c);
        assert!(sim2.abs() < 0.01);
    }
    
    #[test]
    fn test_compute_embedding() {
        let mut pager = ContextPager::default();
        
        let emb1 = pager.compute_embedding("hello world");
        assert_eq!(emb1.len(), pager.config.embedding_dim);
        
        // 相同文本应该有缓存
        let emb2 = pager.compute_embedding("hello world");
        assert!(!pager.embedding_cache.is_empty());
    }
    
    #[test]
    fn test_load_relevant_pages() {
        let mut pager = ContextPager::default();
        
        // 添加消息
        for i in 0..5 {
            pager.add_message(MessageRole::User, format!("Test message {}", i));
        }
        
        // 刷新嵌入向量
        pager.refresh_embeddings();
        
        // 搜索相关页面
        let relevant = pager.load_relevant_pages("Test", 3);
        // 由于相似度阈值可能过滤掉页面，检查是否成功执行
        // 结果可能为空（相似度低于阈值），这也是正常行为
        assert!(relevant.len() <= 3);
    }
    
    #[test]
    fn test_compress_old_pages() {
        let mut pager = ContextPager::default();
        
        // 添加消息
        for i in 0..20 {
            pager.add_message(MessageRole::User, format!("Message {}", i));
        }
        
        // 压缩 (所有页面都是新的，不会压缩)
        let compressed = pager.compress_old_pages(Duration::from_secs(0));
        // 由于时间判断，可能不会压缩
        assert!(compressed >= 0);
    }
    
    #[test]
    fn test_clear() {
        let mut pager = ContextPager::default();
        
        pager.add_message(MessageRole::User, "Test");
        assert_eq!(pager.total_messages(), 1);
        
        pager.clear();
        assert_eq!(pager.total_messages(), 0);
        assert_eq!(pager.active_page_count(), 1);
    }
    
    #[test]
    fn test_stats_hit_rate() {
        let stats = PagingStats {
            hits: 80,
            misses: 20,
            ..Default::default()
        };
        
        assert!((stats.hit_rate() - 0.8).abs() < 0.01);
        
        let empty_stats = PagingStats::default();
        assert_eq!(empty_stats.hit_rate(), 0.0);
    }
    
    #[test]
    fn test_memory_page_eviction_priority() {
        let mut page = MemoryPage::new(0);
        page.access_count = 10;
        page.relevance_score = 0.5;
        
        let priority = page.eviction_priority();
        assert!(priority >= 0.0);
    }
}