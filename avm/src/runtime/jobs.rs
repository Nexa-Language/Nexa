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

//! P1-3: Background Job System Runtime (Rust 版本)
//!
//! Nexa 语言原生的后台任务系统基础实现。
//! 核心特性：
//! - 优先级队列（low/normal/high/critical）
//! - 内存后端（VecDeque）
//! - Job 规格注册、入队/出队/状态查询
//! - 重试逻辑 + exponential backoff

use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

/// Job 优先级
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum JobPriority {
    Low = 0,
    Normal = 1,
    High = 2,
    Critical = 3,
}

impl JobPriority {
    pub fn from_name(name: &str) -> Self {
        match name.to_lowercase() {
            "low" => JobPriority::Low,
            "normal" => JobPriority::Normal,
            "high" => JobPriority::High,
            "critical" => JobPriority::Critical,
            _ => JobPriority::Normal,
        }
    }

    pub fn name(&self) -> &'static str {
        match self {
            JobPriority::Low => "low",
            JobPriority::Normal => "normal",
            JobPriority::High => "high",
            JobPriority::Critical => "critical",
        }
    }
}

/// Job 状态
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JobStatus {
    Pending,
    Running,
    Completed,
    Failed,
    Dead,       // 死信 — 重试耗尽
    Cancelled,
    Expired,
}

impl JobStatus {
    pub fn name(&self) -> &'static str {
        match self {
            JobStatus::Pending => "pending",
            JobStatus::Running => "running",
            JobStatus::Completed => "completed",
            JobStatus::Failed => "failed",
            JobStatus::Dead => "dead",
            JobStatus::Cancelled => "cancelled",
            JobStatus::Expired => "expired",
        }
    }
}

/// 退避策略
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BackoffStrategy {
    Exponential,
    Linear,
    Constant,
}

/// Job 规格
#[derive(Debug, Clone)]
pub struct JobSpec {
    pub name: String,
    pub queue: String,
    pub priority: JobPriority,
    pub retry_count: u32,
    pub timeout_secs: f64,
    pub unique_spec: Option<String>,
    pub unique_duration_secs: f64,
    pub backoff_strategy: BackoffStrategy,
    pub is_agent_job: bool,
    pub agent_name: Option<String>,
}

impl Default for JobSpec {
    fn default() -> Self {
        Self {
            name: String::new(),
            queue: "default".to_string(),
            priority: JobPriority::Normal,
            retry_count: 3,
            timeout_secs: 30.0,
            unique_spec: None,
            unique_duration_secs: 3600.0,
            backoff_strategy: BackoffStrategy::Exponential,
            is_agent_job: false,
            agent_name: None,
        }
    }
}

/// Job 执行记录
#[derive(Debug, Clone)]
pub struct JobRecord {
    pub job_id: String,
    pub spec_name: String,
    pub args: String,  // JSON 字符串
    pub status: JobStatus,
    pub priority: JobPriority,
    pub created_at: f64,
    pub started_at: Option<f64>,
    pub completed_at: Option<f64>,
    pub attempt_count: u32,
    pub max_retries: u32,
    pub last_error: Option<String>,
    pub expires_at: Option<f64>,
    pub unique_key: Option<String>,
    pub unique_expires_at: Option<f64>,
    pub scheduled_at: Option<f64>,
    pub timeout_secs: f64,
    pub queue: String,
}

/// 内存后端 — 使用 VecDeque 优先级队列
pub struct MemoryBackend {
    queues: HashMap<JobPriority, VecDeque<String>>,
    records: HashMap<String, JobRecord>,
    scheduled: Vec<JobRecord>,
    unique_locks: HashMap<String, String>,
}

impl MemoryBackend {
    pub fn new() -> Self {
        let mut queues = HashMap::new();
        queues.insert(JobPriority::Low, VecDeque::new());
        queues.insert(JobPriority::Normal, VecDeque::new());
        queues.insert(JobPriority::High, VecDeque::new());
        queues.insert(JobPriority::Critical, VecDeque::new());

        Self {
            queues,
            records: HashMap::new(),
            scheduled: Vec::new(),
            unique_locks: HashMap::new(),
        }
    }

    fn now_secs() -> f64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64()
    }

    /// 入队一个任务
    pub fn enqueue(&mut self, record: JobRecord) -> Option<String> {
        // 检查唯一去重
        if let Some(unique_key) = &record.unique_key {
            if let Some(existing_id) = self.unique_locks.get(unique_key) {
                if let Some(existing) = self.records.get(existing_id) {
                    if existing.status == JobStatus::Pending || existing.status == JobStatus::Running {
                        if let Some(expires) = existing.unique_expires_at {
                            if self.now_secs() < expires {
                                return None; // 唯一锁未过期，拒绝入队
                            }
                        }
                    }
                }
                // 锁已过期，移除
                self.unique_locks.remove(unique_key);
            }
        }

        let job_id = record.job_id.clone();

        // 如果是延迟任务
        if let Some(scheduled_at) = record.scheduled_at {
            if scheduled_at > self.now_secs() {
                self.scheduled.push(record);
                self.scheduled.sort_by(|a, b| a.scheduled_at.cmp(&b.scheduled_at));
                self.records.insert(job_id.clone(), record);
                if let Some(key) = &record.unique_key {
                    self.unique_locks.insert(key.clone(), job_id.clone());
                }
                return Some(job_id);
            }
        }

        // 正常入队
        self.queues.get_mut(&record.priority).unwrap().push_back(job_id.clone());
        self.records.insert(job_id.clone(), record);
        if let Some(key) = &record.unique_key {
            self.unique_locks.insert(key.clone(), job_id.clone());
        }
        Some(job_id)
    }

    /// 出队最高优先级任务
    pub fn dequeue(&mut self) -> Option<JobRecord> {
        self.promote_scheduled_jobs();

        for priority in [JobPriority::Critical, JobPriority::High, JobPriority::Normal, JobPriority::Low] {
            if let Some(queue) = self.queues.get_mut(&priority) {
                while let Some(job_id) = queue.pop_front() {
                    if let Some(record) = self.records.get_mut(&job_id) {
                        // 检查过期
                        if let Some(expires) = record.expires_at {
                            if self.now_secs() > expires {
                                record.status = JobStatus::Expired;
                                continue;
                            }
                        }
                        // 检查取消
                        if record.status == JobStatus::Cancelled {
                            continue;
                        }
                        record.status = JobStatus::Running;
                        record.started_at = Some(self.now_secs());
                        record.attempt_count += 1;
                        return Some(record.clone());
                    }
                }
            }
        }
        None
    }

    /// 查询任务状态
    pub fn get_status(&self, job_id: &str) -> Option<JobRecord> {
        self.records.get(job_id).cloned()
    }

    /// 取消任务
    pub fn cancel(&mut self, job_id: &str) -> bool {
        if let Some(record) = self.records.get_mut(job_id) {
            if record.status == JobStatus::Pending || record.status == JobStatus::Running {
                record.status = JobStatus::Cancelled;
                record.completed_at = Some(self.now_secs());
                // 从队列移除
                for queue in self.queues.values_mut() {
                    queue.retain(|id| id != job_id);
                }
                // 释放唯一锁
                if let Some(key) = &record.unique_key {
                    if self.unique_locks.get(key) == Some(job_id) {
                        self.unique_locks.remove(key);
                    }
                }
                return true;
            }
        }
        false
    }

    /// 标记完成
    pub fn mark_completed(&mut self, job_id: &str) {
        if let Some(record) = self.records.get_mut(job_id) {
            record.status = JobStatus::Completed;
            record.completed_at = Some(self.now_secs());
            self.release_unique_lock(job_id);
        }
    }

    /// 标记失败 — 返回新状态
    pub fn mark_failed(&mut self, job_id: &str, error: &str, max_retries: u32) -> JobStatus {
        if let Some(record) = self.records.get_mut(job_id) {
            record.last_error = Some(error.to_string());
            if record.attempt_count >= max_retries {
                record.status = JobStatus::Dead;
                record.completed_at = Some(self.now_secs());
                self.release_unique_lock(job_id);
                return JobStatus::Dead;
            } else {
                record.status = JobStatus::Pending;
                record.started_at = None;
                // 重新入队
                self.queues.get_mut(&record.priority).unwrap().push_back(job_id.to_string());
                return JobStatus::Pending;
            }
        }
        JobStatus::Failed
    }

    /// 从死信重试
    pub fn retry_from_dead(&mut self, job_id: &str) -> bool {
        if let Some(record) = self.records.get_mut(job_id) {
            if record.status == JobStatus::Dead {
                record.status = JobStatus::Pending;
                record.attempt_count = 0;
                record.last_error = None;
                record.started_at = None;
                record.completed_at = None;
                self.queues.get_mut(&record.priority).unwrap().push_back(job_id.to_string());
                if let Some(key) = &record.unique_key {
                    self.unique_locks.insert(key.clone(), job_id.to_string());
                }
                return true;
            }
        }
        false
    }

    /// 列出任务
    pub fn list_jobs(&self, status: Option<JobStatus>, limit: usize) -> Vec<JobRecord> {
        let records: Vec<JobRecord> = self.records.values().cloned().collect();
        let filtered = if let Some(s) = status {
            records.into_iter().filter(|r| r.status == s).collect()
        } else {
            records
        };
        let mut sorted = filtered;
        sorted.sort_by(|a, b| b.created_at.cmp(&a.created_at));
        sorted.truncate(limit);
        sorted
    }

    /// 清理已完成任务
    pub fn clear_completed(&mut self) -> usize {
        let to_remove: Vec<String> = self.records.iter()
            .filter(|(_, r)| r.status == JobStatus::Completed || r.status == JobStatus::Expired || r.status == JobStatus::Cancelled)
            .map(|(id, _)| id.clone())
            .collect();
        
        for id in &to_remove {
            if let Some(record) = self.records.get(id) {
                if let Some(key) = &record.unique_key {
                    if self.unique_locks.get(key) == Some(id) {
                        self.unique_locks.remove(key);
                    }
                }
            }
            self.records.remove(id);
        }
        to_remove.len()
    }

    /// 队列统计
    pub fn stats(&self) -> HashMap<String, usize> {
        let mut stats = HashMap::new();
        for status in [JobStatus::Pending, JobStatus::Running, JobStatus::Completed,
                       JobStatus::Failed, JobStatus::Dead, JobStatus::Cancelled, JobStatus::Expired] {
            let count = self.records.values().filter(|r| r.status == status).count();
            stats.insert(status.name().to_string(), count);
        }
        stats.insert("scheduled".to_string(), self.scheduled.len());
        stats
    }

    fn promote_scheduled_jobs(&mut self) {
        let now = self.now_secs();
        while !self.scheduled.is_empty() && self.scheduled[0].scheduled_at.unwrap_or(0.0) <= now {
            let record = self.scheduled.remove(0);
            if let Some(r) = self.records.get_mut(&record.job_id) {
                r.status = JobStatus::Pending;
                self.queues.get_mut(&r.priority).unwrap().push_back(r.job_id.clone());
            }
        }
    }

    fn release_unique_lock(&mut self, job_id: &str) {
        if let Some(record) = self.records.get(job_id) {
            if let Some(key) = &record.unique_key {
                if self.unique_locks.get(key) == Some(job_id) {
                    self.unique_locks.remove(key);
                }
            }
        }
    }
}

/// Job 注册表
pub struct JobRegistry {
    specs: HashMap<String, JobSpec>,
}

impl JobRegistry {
    pub fn new() -> Self {
        Self { specs: HashMap::new() }
    }

    pub fn register(&mut self, spec: JobSpec) {
        self.specs.insert(spec.name.clone(), spec);
    }

    pub fn get(&self, name: &str) -> Option<&JobSpec> {
        self.specs.get(name)
    }

    pub fn list_specs(&self) -> Vec<JobSpec> {
        self.specs.values().cloned().collect()
    }

    pub fn clear(&mut self) {
        self.specs.clear();
    }
}

/// 统一 Job 队列接口
pub struct JobQueue {
    backend: Arc<Mutex<MemoryBackend>>,
    registry: Arc<Mutex<JobRegistry>>,
}

impl JobQueue {
    pub fn new() -> Self {
        Self {
            backend: Arc::new(Mutex::new(MemoryBackend::new())),
            registry: Arc::new(Mutex::new(JobRegistry::new())),
        }
    }

    /// 注册 JobSpec
    pub fn register_spec(&self, spec: JobSpec) {
        self.registry.lock().unwrap().register(spec);
    }

    /// 入队任务
    pub fn enqueue(&self, spec_name: &str, args: &str, options: Option<HashMap<String, String>>) -> Option<String> {
        let registry = self.registry.lock().unwrap();
        let spec = registry.get(spec_name);
        if spec.is_none() {
            return None;
        }
        let spec = spec.unwrap().clone();
        drop(registry);

        let priority = spec.priority;
        let timeout = spec.timeout_secs;
        let max_retries = spec.retry_count;

        // 计算唯一键
        let (unique_key, unique_expires_at) = if spec.unique_spec.is_some() {
            let key = format!("{}:{}", spec_name, simple_hash(args));
            (Some(key), Some(spec.unique_duration_secs + MemoryBackend::now_secs()))
        } else {
            (None, None)
        };

        let record = JobRecord {
            job_id: format!("job-{}", simple_uuid()),
            spec_name: spec_name.to_string(),
            args: args.to_string(),
            status: JobStatus::Pending,
            priority,
            created_at: MemoryBackend::now_secs(),
            started_at: None,
            completed_at: None,
            attempt_count: 0,
            max_retries,
            last_error: None,
            expires_at: None,
            unique_key,
            unique_expires_at,
            scheduled_at: None,
            timeout_secs: timeout,
            queue: spec.queue.clone(),
        };

        self.backend.lock().unwrap().enqueue(record)
    }

    /// 延迟入队
    pub fn enqueue_in(&self, spec_name: &str, delay_secs: f64, args: &str) -> Option<String> {
        let registry = self.registry.lock().unwrap();
        let spec = registry.get(spec_name);
        if spec.is_none() {
            return None;
        }
        let spec = spec.unwrap().clone();
        drop(registry);

        let now = MemoryBackend::now_secs();
        let (unique_key, unique_expires_at) = if spec.unique_spec.is_some() {
            let key = format!("{}:{}", spec_name, simple_hash(args));
            (Some(key), Some(spec.unique_duration_secs + now))
        } else {
            (None, None)
        };

        let record = JobRecord {
            job_id: format!("job-{}", simple_uuid()),
            spec_name: spec_name.to_string(),
            args: args.to_string(),
            status: JobStatus::Pending,
            priority: spec.priority,
            created_at: now,
            started_at: None,
            completed_at: None,
            attempt_count: 0,
            max_retries: spec.retry_count,
            last_error: None,
            expires_at: None,
            unique_key,
            unique_expires_at,
            scheduled_at: Some(now + delay_secs),
            timeout_secs: spec.timeout_secs,
            queue: spec.queue.clone(),
        };

        self.backend.lock().unwrap().enqueue(record)
    }

    /// 查询状态
    pub fn status(&self, job_id: &str) -> Option<JobRecord> {
        self.backend.lock().unwrap().get_status(job_id)
    }

    /// 取消任务
    pub fn cancel(&self, job_id: &str) -> bool {
        self.backend.lock().unwrap().cancel(job_id)
    }

    /// 重试死信
    pub fn retry(&self, job_id: &str) -> bool {
        self.backend.lock().unwrap().retry_from_dead(job_id)
    }

    /// 列出任务
    pub fn list_jobs(&self, status: Option<JobStatus>, limit: usize) -> Vec<JobRecord> {
        self.backend.lock().unwrap().list_jobs(status, limit)
    }

    /// 清理已完成
    pub fn clear_completed(&self) -> usize {
        self.backend.lock().unwrap().clear_completed()
    }

    /// 队列统计
    pub fn stats(&self) -> HashMap<String, usize> {
        self.backend.lock().unwrap().stats()
    }

    /// 出队（Worker 使用）
    pub fn dequeue(&self) -> Option<JobRecord> {
        self.backend.lock().unwrap().dequeue()
    }

    /// 标记完成
    pub fn mark_completed(&self, job_id: &str) {
        self.backend.lock().unwrap().mark_completed(job_id)
    }

    /// 标记失败
    pub fn mark_failed(&self, job_id: &str, error: &str, max_retries: u32) -> JobStatus {
        self.backend.lock().unwrap().mark_failed(job_id, error, max_retries)
    }
}

/// 计算退避延迟
pub fn calculate_backoff(strategy: BackoffStrategy, attempt: u32) -> f64 {
    match strategy {
        BackoffStrategy::Exponential => (2_f64.powi(attempt as i32)).min(300.0),
        BackoffStrategy::Linear => ((attempt as f64) * 10.0).min(300.0),
        BackoffStrategy::Constant => 10.0,
    }
}

// 辅助函数
fn simple_uuid() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default();
    format!("{:x}-{:x}", now.as_secs(), now.subsec_nanos())
}

fn simple_hash(s: &str) -> String {
    // 简易hash（生产环境应使用真正的哈希函数）
    let mut hash: u64 = 0;
    for byte in s.bytes() {
        hash = hash * 31 + byte as u64;
    }
    format!("{:016x}", hash)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_priority_ordering() {
        assert!(JobPriority::Critical > JobPriority::High);
        assert!(JobPriority::High > JobPriority::Normal);
        assert!(JobPriority::Normal > JobPriority::Low);
    }

    #[test]
    fn test_priority_from_name() {
        assert_eq!(JobPriority::from_name("critical"), JobPriority::Critical);
        assert_eq!(JobPriority::from_name("high"), JobPriority::High);
        assert_eq!(JobPriority::from_name("normal"), JobPriority::Normal);
        assert_eq!(JobPriority::from_name("low"), JobPriority::Low);
    }

    #[test]
    fn test_memory_backend_enqueue_dequeue() {
        let mut backend = MemoryBackend::new();
        
        let low_record = JobRecord {
            job_id: "job-low-1".to_string(),
            spec_name: "CleanupLogs".to_string(),
            args: "{}".to_string(),
            status: JobStatus::Pending,
            priority: JobPriority::Low,
            created_at: 1.0,
            started_at: None,
            completed_at: None,
            attempt_count: 0,
            max_retries: 3,
            last_error: None,
            expires_at: None,
            unique_key: None,
            unique_expires_at: None,
            scheduled_at: None,
            timeout_secs: 30.0,
            queue: "logs".to_string(),
        };

        let critical_record = JobRecord {
            job_id: "job-critical-1".to_string(),
            spec_name: "ProcessPayment".to_string(),
            args: "{\"order_id\": \"123\"}".to_string(),
            status: JobStatus::Pending,
            priority: JobPriority::Critical,
            created_at: 2.0,
            started_at: None,
            completed_at: None,
            attempt_count: 0,
            max_retries: 5,
            last_error: None,
            expires_at: None,
            unique_key: None,
            unique_expires_at: None,
            scheduled_at: None,
            timeout_secs: 60.0,
            queue: "payments".to_string(),
        };

        backend.enqueue(low_record);
        backend.enqueue(critical_record);

        // Critical should come first
        let first = backend.dequeue();
        assert!(first.is_some());
        assert_eq!(first.unwrap().priority, JobPriority::Critical);

        let second = backend.dequeue();
        assert!(second.is_some());
        assert_eq!(second.unwrap().priority, JobPriority::Low);
    }

    #[test]
    fn test_memory_backend_cancel() {
        let mut backend = MemoryBackend::new();
        
        let record = JobRecord {
            job_id: "job-1".to_string(),
            spec_name: "TestJob".to_string(),
            args: "{}".to_string(),
            status: JobStatus::Pending,
            priority: JobPriority::Normal,
            created_at: 1.0,
            started_at: None,
            completed_at: None,
            attempt_count: 0,
            max_retries: 3,
            last_error: None,
            expires_at: None,
            unique_key: None,
            unique_expires_at: None,
            scheduled_at: None,
            timeout_secs: 30.0,
            queue: "default".to_string(),
        };

        backend.enqueue(record);
        assert!(backend.cancel("job-1"));
        
        let status = backend.get_status("job-1");
        assert!(status.is_some());
        assert_eq!(status.unwrap().status, JobStatus::Cancelled);
    }

    #[test]
    fn test_memory_backend_unique_dedup() {
        let mut backend = MemoryBackend::new();
        let now = MemoryBackend::now_secs();

        let record1 = JobRecord {
            job_id: "job-1".to_string(),
            spec_name: "SendEmail".to_string(),
            args: "{\"user_id\": \"123\"}".to_string(),
            status: JobStatus::Pending,
            priority: JobPriority::Normal,
            created_at: now,
            started_at: None,
            completed_at: None,
            attempt_count: 0,
            max_retries: 3,
            last_error: None,
            expires_at: None,
            unique_key: Some("SendEmail:abc".to_string()),
            unique_expires_at: Some(now + 3600.0),
            scheduled_at: None,
            timeout_secs: 30.0,
            queue: "emails".to_string(),
        };

        let record2 = JobRecord {
            job_id: "job-2".to_string(),
            spec_name: "SendEmail".to_string(),
            args: "{\"user_id\": \"123\"}".to_string(),
            status: JobStatus::Pending,
            priority: JobPriority::Normal,
            created_at: now,
            started_at: None,
            completed_at: None,
            attempt_count: 0,
            max_retries: 3,
            last_error: None,
            expires_at: None,
            unique_key: Some("SendEmail:abc".to_string()),
            unique_expires_at: Some(now + 3600.0),
            scheduled_at: None,
            timeout_secs: 30.0,
            queue: "emails".to_string(),
        };

        let id1 = backend.enqueue(record1);
        assert!(id1.is_some());

        let id2 = backend.enqueue(record2);
        assert!(id2.is_none()); // 唯一去重冲突
    }

    #[test]
    fn test_calculate_backoff() {
        assert_eq!(calculate_backoff(BackoffStrategy::Exponential, 0), 1.0);
        assert_eq!(calculate_backoff(BackoffStrategy::Exponential, 1), 2.0);
        assert_eq!(calculate_backoff(BackoffStrategy::Exponential, 5), 32.0);
        assert_eq!(calculate_backoff(BackoffStrategy::Linear, 3), 30.0);
        assert_eq!(calculate_backoff(BackoffStrategy::Constant, 5), 10.0);
    }

    #[test]
    fn test_job_queue_interface() {
        let queue = JobQueue::new();
        
        queue.register_spec(JobSpec {
            name: "SendEmail".to_string(),
            queue: "emails".to_string(),
            priority: JobPriority::Normal,
            retry_count: 3,
            timeout_secs: 30.0,
            unique_spec: None,
            unique_duration_secs: 3600.0,
            backoff_strategy: BackoffStrategy::Exponential,
            is_agent_job: false,
            agent_name: None,
        });

        let id = queue.enqueue("SendEmail", "{\"user_id\": \"123\"}", None);
        assert!(id.is_some());

        let status = queue.status(&id.unwrap());
        assert!(status.is_some());
        assert_eq!(status.unwrap().status, JobStatus::Pending);
    }
}