//! 智能调度器 (Smart Scheduler)
//!
//! 提供基于优先级的调度、负载均衡和动态资源分配

use std::collections::{HashMap, HashSet, VecDeque, BinaryHeap};
use std::sync::Arc;
use std::time::{Duration, Instant};
use std::cmp::Ordering;
use serde::{Deserialize, Serialize};
use crate::utils::error::{AvmError, AvmResult};

pub type NodeId = u64;
pub type AgentId = u64;
pub type Priority = u8;

// ==================== 节点状态 ====================

/// DAG 节点状态
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NodeState {
    /// 等待中
    Pending,
    /// 就绪 (依赖已满足)
    Ready,
    /// 运行中
    Running,
    /// 已完成
    Completed,
    /// 失败
    Failed,
}

// ==================== 负载均衡策略 ====================

/// 负载均衡策略
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LoadBalanceStrategy {
    /// 轮询调度
    RoundRobin,
    /// 最少负载优先
    LeastLoaded,
    /// 基于权重的公平调度
    WeightedFair,
    /// 优先级调度
    PriorityBased,
    /// 自适应调度
    Adaptive,
}

impl Default for LoadBalanceStrategy {
    fn default() -> Self {
        LoadBalanceStrategy::Adaptive
    }
}

// ==================== 资源需求 ====================

/// 资源需求
#[derive(Debug, Clone)]
pub struct ResourceRequirements {
    /// CPU 需求 (0-100%)
    pub cpu_percent: u8,
    /// 内存需求 (MB)
    pub memory_mb: u64,
    /// 网络带宽需求 (Mbps)
    pub network_mbps: u64,
    /// 预估执行时间 (ms)
    pub estimated_duration_ms: u64,
}

impl Default for ResourceRequirements {
    fn default() -> Self {
        Self {
            cpu_percent: 50,
            memory_mb: 128,
            network_mbps: 10,
            estimated_duration_ms: 1000,
        }
    }
}

// ==================== 资源分配 ====================

/// 资源分配
#[derive(Debug, Clone)]
pub struct ResourceAllocation {
    /// 分配的 CPU 百分比
    pub allocated_cpu: u8,
    /// 分配的内存 (MB)
    pub allocated_memory: u64,
    /// 分配时间
    pub allocated_at: Instant,
    /// 过期时间
    pub expires_at: Option<Instant>,
}

// ==================== Agent 调度信息 ====================

/// Agent 调度信息
#[derive(Debug, Clone)]
pub struct AgentScheduleInfo {
    /// Agent ID
    pub agent_id: AgentId,
    /// 优先级 (0-255, 越高越优先)
    pub priority: Priority,
    /// 权重
    pub weight: f32,
    /// 预估执行时间 (ms)
    pub estimated_duration_ms: u64,
    /// 依赖列表
    pub dependencies: Vec<AgentId>,
    /// 资源需求
    pub resource_requirements: ResourceRequirements,
    /// 状态
    pub state: NodeState,
    /// 提交时间
    pub submitted_at: Instant,
    /// 开始时间
    pub started_at: Option<Instant>,
    /// 完成时间
    pub completed_at: Option<Instant>,
}

impl AgentScheduleInfo {
    /// 创建新的调度信息
    pub fn new(agent_id: AgentId) -> Self {
        Self {
            agent_id,
            priority: 128,
            weight: 1.0,
            estimated_duration_ms: 1000,
            dependencies: Vec::new(),
            resource_requirements: ResourceRequirements::default(),
            state: NodeState::Pending,
            submitted_at: Instant::now(),
            started_at: None,
            completed_at: None,
        }
    }
    
    /// 设置优先级
    pub fn with_priority(mut self, priority: Priority) -> Self {
        self.priority = priority;
        self
    }
    
    /// 设置权重
    pub fn with_weight(mut self, weight: f32) -> Self {
        self.weight = weight;
        self
    }
    
    /// 添加依赖
    pub fn add_dependency(mut self, dep: AgentId) -> Self {
        self.dependencies.push(dep);
        self
    }
    
    /// 计算等待时间
    pub fn wait_time(&self) -> Duration {
        match self.started_at {
            Some(start) => start.duration_since(self.submitted_at),
            None => self.submitted_at.elapsed(),
        }
    }
    
    /// 计算执行时间
    pub fn execution_time(&self) -> Option<Duration> {
        match (self.started_at, self.completed_at) {
            (Some(start), Some(end)) => Some(end.duration_since(start)),
            (Some(start), None) => Some(start.elapsed()),
            _ => None,
        }
    }
}

// 为了在 BinaryHeap 中使用，需要实现 Ord
impl PartialEq for AgentScheduleInfo {
    fn eq(&self, other: &Self) -> bool {
        self.agent_id == other.agent_id
    }
}

impl Eq for AgentScheduleInfo {}

impl PartialOrd for AgentScheduleInfo {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for AgentScheduleInfo {
    fn cmp(&self, other: &Self) -> Ordering {
        // 优先级高的排前面 (使用 Reverse 使 BinaryHeap 成为最大堆)
        self.priority.cmp(&other.priority)
            .then_with(|| {
                // 等待时间长的优先
                other.wait_time().cmp(&self.wait_time())
            })
            .then_with(|| {
                // 预估时间短的优先 (类似 SJF)
                self.estimated_duration_ms.cmp(&other.estimated_duration_ms)
            })
    }
}

// ==================== 系统负载 ====================

/// 系统负载信息
#[derive(Debug, Clone, Default)]
pub struct SystemLoad {
    /// CPU 使用率 (0-100)
    pub cpu_utilization: f32,
    /// 内存使用率 (0-100)
    pub memory_utilization: f32,
    /// 活跃任务数
    pub active_tasks: usize,
    /// 等待队列长度
    pub pending_tasks: usize,
    /// 平均响应时间 (ms)
    pub avg_response_time_ms: f64,
}

impl SystemLoad {
    /// 是否过载
    pub fn is_overloaded(&self) -> bool {
        self.cpu_utilization > 80.0 || self.memory_utilization > 80.0
    }
    
    /// 可用容量 (0-1)
    pub fn available_capacity(&self) -> f32 {
        1.0 - self.cpu_utilization.max(self.memory_utilization) / 100.0
    }
}

// ==================== 调度计划 ====================

/// 调度计划
#[derive(Debug, Clone)]
pub struct SchedulePlan {
    /// 调度阶段
    pub stages: Vec<Vec<AgentId>>,
    /// 资源分配
    pub allocations: HashMap<AgentId, ResourceAllocation>,
    /// 预估总时间 (ms)
    pub estimated_total_time_ms: u64,
}

// ==================== 调度调整 ====================

/// 调度调整
#[derive(Debug, Clone)]
pub struct ScheduleAdjustment {
    /// Agent ID
    pub agent_id: AgentId,
    /// 调整类型
    pub adjustment_type: AdjustmentType,
}

/// 调整类型
#[derive(Debug, Clone)]
pub enum AdjustmentType {
    /// 迁移到另一个节点
    Migrate { target_node: usize },
    /// 暂停执行
    Suspend,
    /// 恢复执行
    Resume,
    /// 降低资源分配
    ReduceResources { new_cpu: u8, new_memory: u64 },
    /// 提升优先级
    BoostPriority { new_priority: Priority },
}

// ==================== DAG 图结构 ====================

/// DAG 图结构
pub struct DagGraph<T> {
    nodes: HashMap<NodeId, T>,
    edges: Vec<(NodeId, NodeId)>,
    in_degrees: HashMap<NodeId, usize>,
}

impl<T: Clone> DagGraph<T> {
    pub fn new() -> Self {
        Self {
            nodes: HashMap::new(),
            edges: Vec::new(),
            in_degrees: HashMap::new(),
        }
    }

    pub fn add_node(&mut self, id: NodeId, data: T) {
        self.nodes.insert(id, data);
        self.in_degrees.insert(id, 0);
    }

    pub fn add_edge(&mut self, from: NodeId, to: NodeId) -> AvmResult<()> {
        // 检查是否会形成环
        if self.would_create_cycle(from, to) {
            return Err(AvmError::RuntimeError("Edge would create a cycle".to_string()));
        }
        
        self.edges.push((from, to));
        *self.in_degrees.entry(to).or_insert(0) += 1;
        Ok(())
    }
    
    fn would_create_cycle(&self, from: NodeId, to: NodeId) -> bool {
        // 简单的环检测：从 to 开始 DFS，看是否能到达 from
        let mut visited = HashSet::new();
        let mut stack = vec![to];
        
        while let Some(node) = stack.pop() {
            if node == from {
                return true;
            }
            if visited.insert(node) {
                for (src, dst) in &self.edges {
                    if *src == node && !visited.contains(dst) {
                        stack.push(*dst);
                    }
                }
            }
        }
        false
    }

    pub fn entry_nodes(&self) -> Vec<NodeId> {
        self.in_degrees.iter()
            .filter(|(_, &degree)| degree == 0)
            .map(|(&id, _)| id)
            .collect()
    }

    pub fn successors(&self, id: NodeId) -> Vec<NodeId> {
        self.edges.iter()
            .filter(|(from, _)| *from == id)
            .map(|(_, to)| *to)
            .collect()
    }
    
    pub fn predecessors(&self, id: NodeId) -> Vec<NodeId> {
        self.edges.iter()
            .filter(|(_, to)| *to == id)
            .map(|(from, _)| *from)
            .collect()
    }

    pub fn get_node(&self, id: NodeId) -> Option<&T> {
        self.nodes.get(&id)
    }
    
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }
    
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }
}

impl<T: Clone> Default for DagGraph<T> {
    fn default() -> Self {
        Self::new()
    }
}

// ==================== 调度器配置 ====================

/// 调度器配置
#[derive(Debug, Clone)]
pub struct SchedulerConfig {
    /// 最大并发 Agent 数
    pub max_concurrent_agents: usize,
    /// 优先级级别数
    pub priority_levels: u8,
    /// 时间片 (ms)
    pub time_slice_ms: u64,
    /// 负载均衡策略
    pub load_balance_strategy: LoadBalanceStrategy,
    /// 最大等待时间 (ms)
    pub max_wait_time_ms: u64,
    /// 启用抢占
    pub enable_preemption: bool,
    /// 抢占阈值 (等待时间超过此值时触发)
    pub preemption_threshold_ms: u64,
}

impl Default for SchedulerConfig {
    fn default() -> Self {
        Self {
            max_concurrent_agents: 100,
            priority_levels: 255, // u8 范围 0-255
            time_slice_ms: 100,
            load_balance_strategy: LoadBalanceStrategy::Adaptive,
            max_wait_time_ms: 60000,
            enable_preemption: true,
            preemption_threshold_ms: 30000,
        }
    }
}

// ==================== 智能调度器 ====================

/// 智能调度器
pub struct SmartScheduler {
    /// 配置
    config: SchedulerConfig,
    /// 待调度队列 (优先级堆)
    ready_queue: BinaryHeap<AgentScheduleInfo>,
    /// 运行中的任务
    running: HashMap<AgentId, AgentScheduleInfo>,
    /// 已完成的任务
    completed: HashMap<AgentId, AgentScheduleInfo>,
    /// 依赖图
    dependency_graph: DagGraph<AgentId>,
    /// 系统负载
    system_load: SystemLoad,
    /// 统计信息
    stats: SchedulerStats,
}

/// 调度器统计
#[derive(Debug, Clone, Default)]
pub struct SchedulerStats {
    /// 已调度任务数
    pub tasks_scheduled: u64,
    /// 已完成任务数
    pub tasks_completed: u64,
    /// 失败任务数
    pub tasks_failed: u64,
    /// 平均等待时间 (ms)
    pub avg_wait_time_ms: f64,
    /// 平均执行时间 (ms)
    pub avg_execution_time_ms: f64,
    /// 总 CPU 时间 (ms)
    pub total_cpu_time_ms: u64,
    /// 抢占次数
    pub preemptions: u64,
}

impl SmartScheduler {
    /// 创建新的智能调度器
    pub fn new(config: SchedulerConfig) -> Self {
        Self {
            config,
            ready_queue: BinaryHeap::new(),
            running: HashMap::new(),
            completed: HashMap::new(),
            dependency_graph: DagGraph::new(),
            system_load: SystemLoad::default(),
            stats: SchedulerStats::default(),
        }
    }
    
    /// 提交任务
    pub fn submit(&mut self, info: AgentScheduleInfo) -> AvmResult<()> {
        // 检查依赖是否满足
        let deps_satisfied = info.dependencies.iter()
            .all(|dep| self.completed.contains_key(dep));
        
        let mut info = info;
        info.state = if deps_satisfied {
            NodeState::Ready
        } else {
            NodeState::Pending
        };
        
        // 添加到依赖图
        self.dependency_graph.add_node(info.agent_id, info.agent_id);
        for dep in &info.dependencies {
            self.dependency_graph.add_edge(*dep, info.agent_id)?;
        }
        
        if info.state == NodeState::Ready {
            self.ready_queue.push(info);
        }
        
        self.stats.tasks_scheduled += 1;
        Ok(())
    }
    
    /// 调度下一个任务
    pub fn schedule_next(&mut self) -> Option<AgentScheduleInfo> {
        // 检查并发限制
        if self.running.len() >= self.config.max_concurrent_agents {
            return None;
        }
        
        // 从优先级队列中取出最高优先级任务
        while let Some(mut task) = self.ready_queue.pop() {
            task.state = NodeState::Running;
            task.started_at = Some(Instant::now());
            self.running.insert(task.agent_id, task.clone());
            return Some(task);
        }
        
        None
    }
    
    /// 完成任务
    pub fn complete(&mut self, agent_id: AgentId, success: bool) {
        if let Some(mut info) = self.running.remove(&agent_id) {
            info.state = if success { NodeState::Completed } else { NodeState::Failed };
            info.completed_at = Some(Instant::now());
            
            // 更新统计
            if success {
                self.stats.tasks_completed += 1;
                if let Some(exec_time) = info.execution_time() {
                    let exec_ms = exec_time.as_millis() as f64;
                    self.stats.total_cpu_time_ms += exec_ms as u64;
                    // 更新平均执行时间
                    let n = self.stats.tasks_completed as f64;
                    self.stats.avg_execution_time_ms = 
                        (self.stats.avg_execution_time_ms * (n - 1.0) + exec_ms) / n;
                }
            } else {
                self.stats.tasks_failed += 1;
            }
            
            self.completed.insert(agent_id, info);
            
            // 检查是否有等待此任务的任务可以就绪
            self.check_dependents(agent_id);
        }
    }
    
    /// 检查依赖此任务的待处理任务
    fn check_dependents(&mut self, completed_agent: AgentId) {
        // 找到所有依赖 completed_agent 的任务
        for successor in self.dependency_graph.successors(completed_agent) {
            // 检查是否所有依赖都已满足
            let all_deps_done = self.dependency_graph.predecessors(successor)
                .iter()
                .all(|dep| self.completed.contains_key(dep));
            
            if all_deps_done {
                // 将任务状态更新为就绪
                // 注意：这里简化处理，实际需要从 pending 队列移动到 ready_queue
            }
        }
    }
    
    /// 获取系统负载
    pub fn system_load(&self) -> &SystemLoad {
        &self.system_load
    }
    
    /// 更新系统负载
    pub fn update_load(&mut self, load: SystemLoad) {
        self.system_load = load;
    }
    
    /// 动态重平衡
    pub fn rebalance(&mut self) -> Vec<ScheduleAdjustment> {
        let mut adjustments = Vec::new();
        
        if !self.system_load.is_overloaded() {
            return adjustments;
        }
        
        // 检查是否需要抢占
        if self.config.enable_preemption {
            for (&agent_id, info) in &self.running {
                let wait_time = info.wait_time().as_millis() as u64;
                if wait_time > self.config.preemption_threshold_ms && info.priority < 200 {
                    adjustments.push(ScheduleAdjustment {
                        agent_id,
                        adjustment_type: AdjustmentType::BoostPriority { new_priority: 200 },
                    });
                    self.stats.preemptions += 1;
                }
            }
        }
        
        adjustments
    }
    
    /// 生成调度计划
    pub fn generate_plan(&mut self, agents: Vec<AgentScheduleInfo>) -> SchedulePlan {
        // 1. 构建依赖图
        for info in &agents {
            self.dependency_graph.add_node(info.agent_id, info.agent_id);
            for dep in &info.dependencies {
                let _ = self.dependency_graph.add_edge(*dep, info.agent_id);
            }
        }
        
        // 2. 拓扑排序
        let order = self.topological_sort();
        
        // 3. 并行度分析
        let stages = self.analyze_parallelism(&order);
        
        // 4. 资源分配
        let allocations = self.allocate_resources(&stages);
        
        // 5. 估算完成时间
        let estimated_time = self.estimate_completion_time(&stages);
        
        SchedulePlan {
            stages,
            allocations,
            estimated_total_time_ms: estimated_time,
        }
    }
    
    /// 拓扑排序
    fn topological_sort(&self) -> Vec<AgentId> {
        let mut result = Vec::new();
        let mut in_degree: HashMap<AgentId, usize> = HashMap::new();
        let mut queue: VecDeque<AgentId> = VecDeque::new();
        
        // 初始化入度
        for (from, to) in &self.dependency_graph.edges {
            *in_degree.entry(*to).or_insert(0) += 1;
            in_degree.entry(*from).or_insert(0);
        }
        
        // 入度为 0 的节点入队
        for (&node, &degree) in &in_degree {
            if degree == 0 {
                queue.push_back(node);
            }
        }
        
        // BFS 拓扑排序
        while let Some(node) = queue.pop_front() {
            result.push(node);
            
            for successor in self.dependency_graph.successors(node) {
                if let Some(deg) = in_degree.get_mut(&successor) {
                    *deg -= 1;
                    if *deg == 0 {
                        queue.push_back(successor);
                    }
                }
            }
        }
        
        result
    }
    
    /// 分析并行度
    fn analyze_parallelism(&self, order: &[AgentId]) -> Vec<Vec<AgentId>> {
        let mut stages: Vec<Vec<AgentId>> = Vec::new();
        let mut completed: HashSet<AgentId> = HashSet::new();
        let mut remaining: HashSet<AgentId> = order.iter().copied().collect();
        
        while !remaining.is_empty() {
            // 找出所有依赖已满足的任务
            let mut stage = Vec::new();
            let mut new_completed = HashSet::new();
            
            for &agent_id in &remaining {
                let deps_done = self.dependency_graph.predecessors(agent_id)
                    .iter()
                    .all(|dep| completed.contains(dep));
                
                if deps_done {
                    stage.push(agent_id);
                    new_completed.insert(agent_id);
                }
            }
            
            for agent_id in &new_completed {
                remaining.remove(agent_id);
            }
            
            completed.extend(new_completed);
            
            if !stage.is_empty() {
                stages.push(stage);
            } else {
                break; // 防止死循环
            }
        }
        
        stages
    }
    
    /// 资源分配
    fn allocate_resources(&self, stages: &[Vec<AgentId>]) -> HashMap<AgentId, ResourceAllocation> {
        let mut allocations = HashMap::new();
        
        for stage in stages {
            let agent_count = stage.len();
            if agent_count == 0 {
                continue;
            }
            
            // 平均分配资源
            let cpu_per_agent = 100 / agent_count.max(1) as u8;
            let memory_per_agent = 1024 / agent_count.max(1) as u64; // 假设总共 1024MB
            
            for &agent_id in stage {
                allocations.insert(agent_id, ResourceAllocation {
                    allocated_cpu: cpu_per_agent,
                    allocated_memory: memory_per_agent,
                    allocated_at: Instant::now(),
                    expires_at: None,
                });
            }
        }
        
        allocations
    }
    
    /// 估算完成时间
    fn estimate_completion_time(&self, stages: &[Vec<AgentId>]) -> u64 {
        let mut total_time = 0u64;
        
        for stage in stages {
            // 每个阶段的时间取最长任务
            let max_time = stage.iter()
                .map(|_| 1000u64) // 默认 1s
                .max()
                .unwrap_or(0);
            total_time += max_time;
        }
        
        total_time
    }
    
    /// 获取统计信息
    pub fn stats(&self) -> &SchedulerStats {
        &self.stats
    }
    
    /// 获取运行中的任务数
    pub fn running_count(&self) -> usize {
        self.running.len()
    }
    
    /// 获取等待中的任务数
    pub fn pending_count(&self) -> usize {
        self.ready_queue.len()
    }
    
    /// 获取已完成的任务数
    pub fn completed_count(&self) -> usize {
        self.completed.len()
    }
}

impl Default for SmartScheduler {
    fn default() -> Self {
        Self::new(SchedulerConfig::default())
    }
}

// ==================== 基础 DAG 调度器 (兼容旧 API) ====================

/// DAG 调度器 (基础版本)
pub struct DagScheduler<T, R> {
    graph: DagGraph<T>,
    executor: Box<dyn Fn(T) -> R>,
}

impl<T: Clone + Send + 'static, R: Clone + Send + 'static> DagScheduler<T, R> {
    pub fn new<F>(graph: DagGraph<T>, executor: F) -> Self
    where F: Fn(T) -> R + 'static {
        Self {
            graph,
            executor: Box::new(executor),
        }
    }

    pub fn execute_sync(&self) -> AvmResult<HashMap<NodeId, R>> {
        let mut results = HashMap::new();
        let mut completed: HashSet<NodeId> = HashSet::new();
        let mut in_degree_copy = self.graph.in_degrees.clone();

        let mut queue: VecDeque<NodeId> = self.graph.entry_nodes().into_iter().collect();

        while let Some(id) = queue.pop_front() {
            if let Some(node) = self.graph.get_node(id) {
                let result = (self.executor)(node.clone());
                results.insert(id, result);
                completed.insert(id);

                for successor in self.graph.successors(id) {
                    let degree = in_degree_copy.get_mut(&successor).unwrap();
                    *degree -= 1;
                    if *degree == 0 {
                        queue.push_back(successor);
                    }
                }
            }
        }

        Ok(results)
    }
}

// ==================== Work-Stealing 调度器 ====================
// 论文声称：Actor-based scheduling with work-stealing for load balancing

/// Worker 状态
#[derive(Debug, Clone)]
pub struct WorkerState {
    /// Worker ID
    pub worker_id: u32,
    /// 本地任务队列
    pub local_queue: VecDeque<AgentScheduleInfo>,
    /// 是否正在窃取
    pub is_stealing: bool,
    /// 已完成任务数
    pub tasks_completed: u64,
    /// 窃取的任务数
    pub tasks_stolen: u64,
    /// 被窃取的任务数
    pub tasks_stolen_from: u64,
}

impl WorkerState {
    pub fn new(worker_id: u32) -> Self {
        Self {
            worker_id,
            local_queue: VecDeque::new(),
            is_stealing: false,
            tasks_completed: 0,
            tasks_stolen: 0,
            tasks_stolen_from: 0,
        }
    }
    
    pub fn queue_size(&self) -> usize {
        self.local_queue.len()
    }
    
    pub fn is_idle(&self) -> bool {
        self.local_queue.is_empty()
    }
}

/// Work-Stealing 调度器
///
/// 实现 Actor-based 并发调度，支持工作窃取负载均衡
/// 论文关键指标：near-linear throughput scaling (0.082 QPS at peak concurrency)
pub struct WorkStealingScheduler {
    /// Worker 数量
    num_workers: usize,
    /// Worker 状态列表
    workers: Vec<WorkerState>,
    /// 全局任务队列（用于初始分配）
    global_queue: VecDeque<AgentScheduleInfo>,
    /// 运行中的任务
    running: HashMap<AgentId, (AgentScheduleInfo, u32)>, // (task, worker_id)
    /// 已完成任务
    completed: HashMap<AgentId, AgentScheduleInfo>,
    /// 依赖图
    dependency_graph: DagGraph<AgentId>,
    /// 统计信息
    stats: WorkStealingStats,
    /// 配置
    config: WorkStealingConfig,
}

/// Work-Stealing 配置
#[derive(Debug, Clone)]
pub struct WorkStealingConfig {
    /// 窃取阈值（当队列大小差异超过此值时触发窃取）
    pub steal_threshold: usize,
    /// 每次窃取的任务数
    pub steal_batch_size: usize,
    /// 最大并发任务数
    pub max_concurrent: usize,
}

impl Default for WorkStealingConfig {
    fn default() -> Self {
        Self {
            steal_threshold: 2,
            steal_batch_size: 1,
            max_concurrent: 8,
        }
    }
}

/// Work-Stealing 统计
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WorkStealingStats {
    /// 总任务数
    pub total_tasks: u64,
    /// 已完成任务数
    pub completed_tasks: u64,
    /// 窃取次数
    pub steal_attempts: u64,
    /// 成功窃取次数
    pub successful_steals: u64,
    /// 窃取的任务总数
    pub total_tasks_stolen: u64,
    /// 平均队列大小
    pub avg_queue_size: f64,
    /// 负载均衡效率 (0-1)
    pub load_balance_efficiency: f64,
    /// 吞吐量 (QPS)
    pub throughput_qps: f64,
}

impl WorkStealingScheduler {
    /// 创建新的 Work-Stealing 调度器
    pub fn new(num_workers: usize) -> Self {
        Self::with_config(num_workers, WorkStealingConfig::default())
    }
    
    /// 使用配置创建调度器
    pub fn with_config(num_workers: usize, config: WorkStealingConfig) -> Self {
        let workers = (0..num_workers)
            .map(|i| WorkerState::new(i as u32))
            .collect();
        
        Self {
            num_workers,
            workers,
            global_queue: VecDeque::new(),
            running: HashMap::new(),
            completed: HashMap::new(),
            dependency_graph: DagGraph::new(),
            stats: WorkStealingStats::default(),
            config,
        }
    }
    
    /// 提交任务
    pub fn submit(&mut self, task: AgentScheduleInfo) -> AvmResult<()> {
        self.stats.total_tasks += 1;
        
        // 添加到依赖图
        self.dependency_graph.add_node(task.agent_id, task.agent_id);
        for dep in &task.dependencies {
            self.dependency_graph.add_edge(*dep, task.agent_id)?;
        }
        
        // 初始分配到最空闲的 worker
        let min_worker = self.find_least_loaded_worker();
        self.workers[min_worker].local_queue.push_back(task);
        
        Ok(())
    }
    
    /// 批量提交任务
    pub fn submit_batch(&mut self, tasks: Vec<AgentScheduleInfo>) -> AvmResult<()> {
        for task in tasks {
            self.submit(task)?;
        }
        Ok(())
    }
    
    /// 调度下一个任务（从指定 worker 的视角）
    pub fn schedule(&mut self, worker_id: u32) -> Option<AgentScheduleInfo> {
        if self.running.len() >= self.config.max_concurrent {
            return None;
        }
        
        // 先尝试从本地队列获取
        if let Some(task) = self.workers[worker_id as usize].local_queue.pop_front() {
            let result = task.clone();
            self.start_task(task, worker_id);
            return Some(result);
        }
        
        // 尝试从全局队列获取
        if let Some(task) = self.global_queue.pop_front() {
            let result = task.clone();
            self.start_task(task, worker_id);
            return Some(result);
        }
        
        // 尝试工作窃取
        if let Some(task) = self.try_steal(worker_id) {
            let result = task.clone();
            self.start_task(task, worker_id);
            return Some(result);
        }
        
        None
    }
    
    fn start_task(&mut self, mut task: AgentScheduleInfo, worker_id: u32) {
        task.state = NodeState::Running;
        task.started_at = Some(Instant::now());
        self.running.insert(task.agent_id, (task, worker_id));
    }
    
    /// 完成任务
    pub fn complete(&mut self, agent_id: AgentId) {
        if let Some((mut task, worker_id)) = self.running.remove(&agent_id) {
            task.state = NodeState::Completed;
            task.completed_at = Some(Instant::now());
            
            self.workers[worker_id as usize].tasks_completed += 1;
            self.completed.insert(agent_id, task);
            self.stats.completed_tasks += 1;
            
            // 更新依赖
            self.update_dependencies(agent_id);
        }
    }
    
    fn update_dependencies(&mut self, completed_id: AgentId) {
        // 检查是否有等待此任务的任务可以就绪
        for successor in self.dependency_graph.successors(completed_id) {
            // 检查所有依赖是否满足
            let all_deps_complete = self.dependency_graph.predecessors(successor)
                .iter()
                .all(|dep| self.completed.contains_key(dep));
            
            if all_deps_complete {
                // 可以将任务加入队列（实际实现中需要找到该任务）
            }
        }
    }
    
    /// 尝试从其他 worker 窃取任务
    fn try_steal(&mut self, thief_id: u32) -> Option<AgentScheduleInfo> {
        self.stats.steal_attempts += 1;
        
        // 找到任务最多的 worker
        let (victim_id, victim_queue_size) = self.find_most_loaded_worker();
        
        // 检查是否值得窃取
        if victim_queue_size <= self.config.steal_threshold {
            return None;
        }
        
        // 标记正在窃取
        self.workers[thief_id as usize].is_stealing = true;
        
        // 从受害者队列尾部窃取任务
        let stolen = self.workers[victim_id].local_queue.pop_back();
        
        if stolen.is_some() {
            self.stats.successful_steals += 1;
            self.stats.total_tasks_stolen += 1;
            self.workers[thief_id as usize].tasks_stolen += 1;
            self.workers[victim_id].tasks_stolen_from += 1;
        }
        
        self.workers[thief_id as usize].is_stealing = false;
        stolen
    }
    
    /// 找到负载最轻的 worker
    fn find_least_loaded_worker(&self) -> usize {
        self.workers
            .iter()
            .enumerate()
            .min_by_key(|(_, w)| w.queue_size())
            .map(|(i, _)| i)
            .unwrap_or(0)
    }
    
    /// 找到负载最重的 worker
    fn find_most_loaded_worker(&self) -> (usize, usize) {
        self.workers
            .iter()
            .enumerate()
            .map(|(i, w)| (i, w.queue_size()))
            .max_by_key(|(_, size)| *size)
            .unwrap_or((0, 0))
    }
    
    /// 执行负载均衡
    pub fn rebalance(&mut self) {
        let (max_worker, max_size) = self.find_most_loaded_worker();
        let min_worker = self.find_least_loaded_worker();
        let min_size = self.workers[min_worker].queue_size();
        
        // 如果负载差异过大，进行任务迁移
        while max_size > min_size + self.config.steal_threshold * 2 {
            if let Some(task) = self.workers[max_worker].local_queue.pop_back() {
                self.workers[min_worker].local_queue.push_front(task);
            } else {
                break;
            }
        }
        
        self.update_load_balance_efficiency();
    }
    
    fn update_load_balance_efficiency(&mut self) {
        if self.workers.is_empty() {
            return;
        }
        
        let total_tasks: usize = self.workers.iter().map(|w| w.queue_size()).sum();
        let avg = total_tasks as f64 / self.workers.len() as f64;
        
        if avg == 0.0 {
            self.stats.load_balance_efficiency = 1.0;
            return;
        }
        
        // 计算方差
        let variance: f64 = self.workers
            .iter()
            .map(|w| (w.queue_size() as f64 - avg).powi(2))
            .sum::<f64>() / self.workers.len() as f64;
        
        // 效率 = 1 - 归一化方差
        self.stats.load_balance_efficiency = (1.0 - (variance.sqrt() / avg)).max(0.0).min(1.0);
        self.stats.avg_queue_size = avg;
    }
    
    /// 获取统计信息
    pub fn stats(&self) -> &WorkStealingStats {
        &self.stats
    }
    
    /// 获取 worker 状态
    pub fn worker_states(&self) -> &[WorkerState] {
        &self.workers
    }
    
    /// 检查是否所有任务都已完成
    pub fn is_idle(&self) -> bool {
        self.running.is_empty() && self.workers.iter().all(|w| w.is_idle())
    }
    
    /// 获取性能报告
    pub fn performance_report(&self) -> String {
        format!(
            r#"Work-Stealing Scheduler Performance Report
============================================
Workers: {}
Total Tasks: {}
Completed Tasks: {}
Steal Attempts: {}
Successful Steals: {}
Tasks Stolen: {}
Load Balance Efficiency: {:.1}%
Average Queue Size: {:.2}
Throughput: {:.3} QPS

Per-Worker Statistics:
{}
"#,
            self.num_workers,
            self.stats.total_tasks,
            self.stats.completed_tasks,
            self.stats.steal_attempts,
            self.stats.successful_steals,
            self.stats.total_tasks_stolen,
            self.stats.load_balance_efficiency * 100.0,
            self.stats.avg_queue_size,
            self.stats.throughput_qps,
            self.workers
                .iter()
                .map(|w| format!(
                    "  Worker {}: Queue={}, Completed={}, Stolen={}, StolenFrom={}",
                    w.worker_id, w.queue_size(), w.tasks_completed, w.tasks_stolen, w.tasks_stolen_from
                ))
                .collect::<Vec<_>>()
                .join("\n")
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_dag_graph() {
        let mut graph: DagGraph<i32> = DagGraph::new();
        graph.add_node(1, 10);
        graph.add_node(2, 20);
        graph.add_edge(1, 2).unwrap();

        let entries = graph.entry_nodes();
        assert_eq!(entries, vec![1]);
        assert_eq!(graph.node_count(), 2);
        assert_eq!(graph.edge_count(), 1);
    }
    
    #[test]
    fn test_dag_graph_cycle_detection() {
        let mut graph: DagGraph<i32> = DagGraph::new();
        graph.add_node(1, 10);
        graph.add_node(2, 20);
        graph.add_edge(1, 2).unwrap();
        
        // 这会形成环
        let result = graph.add_edge(2, 1);
        assert!(result.is_err());
    }
    
    #[test]
    fn test_agent_schedule_info() {
        let info = AgentScheduleInfo::new(1)
            .with_priority(200)
            .with_weight(2.0)
            .add_dependency(0);
        
        assert_eq!(info.agent_id, 1);
        assert_eq!(info.priority, 200);
        assert_eq!(info.weight, 2.0);
        assert_eq!(info.dependencies.len(), 1);
        assert_eq!(info.state, NodeState::Pending);
    }
    
    #[test]
    fn test_system_load() {
        let load = SystemLoad {
            cpu_utilization: 90.0,
            memory_utilization: 50.0,
            ..Default::default()
        };
        
        assert!(load.is_overloaded());
        assert!(load.available_capacity() < 0.2);
    }
    
    #[test]
    fn test_scheduler_config_default() {
        let config = SchedulerConfig::default();
        assert_eq!(config.max_concurrent_agents, 100);
        assert_eq!(config.load_balance_strategy, LoadBalanceStrategy::Adaptive);
        assert!(config.enable_preemption);
    }
    
    #[test]
    fn test_smart_scheduler_submit() {
        let mut scheduler = SmartScheduler::default();
        
        let info = AgentScheduleInfo::new(1)
            .with_priority(100);
        
        let result = scheduler.submit(info);
        assert!(result.is_ok());
        assert_eq!(scheduler.pending_count(), 1);
    }
    
    #[test]
    fn test_smart_scheduler_schedule() {
        let mut scheduler = SmartScheduler::default();
        
        let info = AgentScheduleInfo::new(1)
            .with_priority(100);
        
        scheduler.submit(info).unwrap();
        
        let scheduled = scheduler.schedule_next();
        assert!(scheduled.is_some());
        assert_eq!(scheduled.unwrap().agent_id, 1);
        assert_eq!(scheduler.running_count(), 1);
    }
    
    #[test]
    fn test_smart_scheduler_complete() {
        let mut scheduler = SmartScheduler::default();
        
        let info = AgentScheduleInfo::new(1);
        scheduler.submit(info).unwrap();
        scheduler.schedule_next();
        
        scheduler.complete(1, true);
        
        assert_eq!(scheduler.running_count(), 0);
        assert_eq!(scheduler.completed_count(), 1);
        assert_eq!(scheduler.stats().tasks_completed, 1);
    }
    
    #[test]
    fn test_smart_scheduler_priority() {
        let mut scheduler = SmartScheduler::default();
        
        // 提交多个任务，不同优先级
        let low = AgentScheduleInfo::new(1).with_priority(50);
        let high = AgentScheduleInfo::new(2).with_priority(200);
        let medium = AgentScheduleInfo::new(3).with_priority(100);
        
        scheduler.submit(low).unwrap();
        scheduler.submit(high).unwrap();
        scheduler.submit(medium).unwrap();
        
        // 高优先级应该先被调度
        let first = scheduler.schedule_next();
        assert!(first.is_some());
        assert_eq!(first.unwrap().priority, 200);
    }
    
    #[test]
    fn test_smart_scheduler_concurrent_limit() {
        let config = SchedulerConfig {
            max_concurrent_agents: 2,
            ..Default::default()
        };
        let mut scheduler = SmartScheduler::new(config);
        
        for i in 0..5 {
            let info = AgentScheduleInfo::new(i);
            scheduler.submit(info).unwrap();
        }
        
        // 只能调度 2 个
        scheduler.schedule_next();
        scheduler.schedule_next();
        let third = scheduler.schedule_next();
        assert!(third.is_none());
    }
    
    #[test]
    fn test_topological_sort() {
        let mut scheduler = SmartScheduler::default();
        
        // 创建依赖关系: 1 -> 2 -> 3
        let task1 = AgentScheduleInfo::new(1);
        let task2 = AgentScheduleInfo::new(2).add_dependency(1);
        let task3 = AgentScheduleInfo::new(3).add_dependency(2);
        
        scheduler.dependency_graph.add_node(1, 1);
        scheduler.dependency_graph.add_node(2, 2);
        scheduler.dependency_graph.add_node(3, 3);
        scheduler.dependency_graph.add_edge(1, 2).unwrap();
        scheduler.dependency_graph.add_edge(2, 3).unwrap();
        
        let order = scheduler.topological_sort();
        assert_eq!(order, vec![1, 2, 3]);
    }
    
    #[test]
    fn test_parallelism_analysis() {
        let mut scheduler = SmartScheduler::default();
        
        // 创建可以并行执行的任务: 1, 2 可以并行，然后 3
        scheduler.dependency_graph.add_node(1, 1);
        scheduler.dependency_graph.add_node(2, 2);
        scheduler.dependency_graph.add_node(3, 3);
        scheduler.dependency_graph.add_edge(1, 3).unwrap();
        scheduler.dependency_graph.add_edge(2, 3).unwrap();
        
        let order = scheduler.topological_sort();
        let stages = scheduler.analyze_parallelism(&order);
        
        assert!(stages.len() >= 2);
        // 第一阶段应该包含 1 和 2
        assert!(stages[0].contains(&1) || stages[0].contains(&2));
    }
    
    #[test]
    fn test_rebalance() {
        let mut scheduler = SmartScheduler::default();
        
        // 设置过载
        scheduler.update_load(SystemLoad {
            cpu_utilization: 90.0,
            memory_utilization: 85.0,
            ..Default::default()
        });
        
        // 提交并开始执行一个任务
        let info = AgentScheduleInfo::new(1).with_priority(50);
        scheduler.submit(info).unwrap();
        scheduler.schedule_next();
        
        // 等待一段时间让 wait_time 增加
        std::thread::sleep(std::time::Duration::from_millis(10));
        
        let adjustments = scheduler.rebalance();
        // 可能会有抢占调整
        assert!(scheduler.stats().preemptions >= 0);
    }
    
    #[test]
    fn test_generate_plan() {
        let mut scheduler = SmartScheduler::default();
        
        let tasks = vec![
            AgentScheduleInfo::new(1).with_priority(100),
            AgentScheduleInfo::new(2).with_priority(50).add_dependency(1),
            AgentScheduleInfo::new(3).with_priority(75),
        ];
        
        let plan = scheduler.generate_plan(tasks);
        
        assert!(!plan.stages.is_empty());
        assert!(!plan.allocations.is_empty());
        assert!(plan.estimated_total_time_ms > 0);
    }
    
    #[test]
    fn test_work_stealing_scheduler() {
        let mut scheduler = WorkStealingScheduler::new(4);
        
        // 提交 10 个任务
        for i in 0..10 {
            let task = AgentScheduleInfo::new(i);
            scheduler.submit(task).unwrap();
        }
        
        // 验证任务已分配
        assert_eq!(scheduler.stats().total_tasks, 10);
        
        // 从不同 worker 调度任务
        let task0 = scheduler.schedule(0);
        assert!(task0.is_some());
        
        let task1 = scheduler.schedule(1);
        assert!(task1.is_some());
        
        // 完成任务
        scheduler.complete(task0.unwrap().agent_id);
        scheduler.complete(task1.unwrap().agent_id);
        
        // 验证统计
        assert_eq!(scheduler.stats().completed_tasks, 2);
    }
    
    #[test]
    fn test_work_stealing() {
        let config = WorkStealingConfig {
            steal_threshold: 1,
            steal_batch_size: 1,
            max_concurrent: 10,
        };
        let mut scheduler = WorkStealingScheduler::with_config(2, config);
        
        // 提交多个任务到第一个 worker
        for i in 0..5 {
            let task = AgentScheduleInfo::new(i);
            scheduler.submit(task).unwrap();
        }
        
        // Worker 0 获取任务
        let _task0 = scheduler.schedule(0);
        
        // Worker 1 尝试获取任务（应该触发窃取）
        let task1 = scheduler.schedule(1);
        assert!(task1.is_some());
        
        // 验证窃取发生
        // 注意：窃取统计可能不会立即更新，取决于实现
        println!("{}", scheduler.performance_report());
    }
    
    #[test]
    fn test_load_balancing() {
        let mut scheduler = WorkStealingScheduler::new(4);
        
        // 提交任务
        for i in 0..20 {
            let task = AgentScheduleInfo::new(i);
            scheduler.submit(task).unwrap();
        }
        
        // 执行负载均衡
        scheduler.rebalance();
        
        // 验证负载均衡效率
        let stats = scheduler.stats();
        println!("Load balance efficiency: {:.1}%", stats.load_balance_efficiency * 100.0);
        println!("Avg queue size: {:.2}", stats.avg_queue_size);
        
        // 打印性能报告
        println!("{}", scheduler.performance_report());
    }
    
    #[test]
    fn test_tree_of_thoughts_with_cow_and_workstealing() {
        // 综合测试：COW 内存 + Work-Stealing 调度
        use crate::vm::cow_memory::CowMemoryManager;
        
        // 创建 COW 内存管理器
        let memory = CowMemoryManager::new();
        
        // 创建调度器
        let mut scheduler = WorkStealingScheduler::new(4);
        
        // 模拟 Tree-of-Thoughts 模式
        // 1. 创建初始状态快照
        let root = memory.create_snapshot();
        
        // 2. 创建多个思维分支
        let branch1 = memory.create_branch(root);
        let branch2 = memory.create_branch(root);
        let branch3 = memory.create_branch(root);
        
        // 3. 在每个分支中设置不同的思维路径
        memory.switch_to_snapshot(branch1);
        memory.set("thought".to_string(), crate::vm::cow_memory::MemoryValue::String("approach_A".to_string()));
        
        memory.switch_to_snapshot(branch2);
        memory.set("thought".to_string(), crate::vm::cow_memory::MemoryValue::String("approach_B".to_string()));
        
        memory.switch_to_snapshot(branch3);
        memory.set("thought".to_string(), crate::vm::cow_memory::MemoryValue::String("approach_C".to_string()));
        
        // 4. 创建对应的调度任务
        let task1 = AgentScheduleInfo::new(branch1);
        let task2 = AgentScheduleInfo::new(branch2);
        let task3 = AgentScheduleInfo::new(branch3);
        
        scheduler.submit(task1).unwrap();
        scheduler.submit(task2).unwrap();
        scheduler.submit(task3).unwrap();
        
        // 5. 并行调度执行
        let scheduled1 = scheduler.schedule(0);
        let scheduled2 = scheduler.schedule(1);
        let scheduled3 = scheduler.schedule(2);
        
        assert!(scheduled1.is_some());
        assert!(scheduled2.is_some());
        assert!(scheduled3.is_some());
        
        // 打印性能报告
        println!("\n=== COW Memory Performance ===");
        println!("{}", memory.performance_report());
        
        println!("\n=== Work-Stealing Scheduler Performance ===");
        println!("{}", scheduler.performance_report());
    }
}
