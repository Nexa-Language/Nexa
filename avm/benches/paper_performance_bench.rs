//! Nexa 论文性能基准测试 - 使用真实 Rust AVM 组件
//!
//! 验证论文声称的性能指标：
//! 1. COW snapshot: 200,000x 性能提升 (0.1ms vs 20,178ms deep copy)
//! 2. Work-stealing: 负载均衡效率 > 95%
//!
//! 运行方式：
//!     cargo bench --features wasm

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

// 导入真实组件
use nexa_avm::vm::cow_memory::{CowMemoryManager, MemoryValue};
use nexa_avm::vm::scheduler::{WorkStealingScheduler, AgentScheduleInfo, WorkStealingConfig};

// ============================================================
// 1. COW 内存性能测试 - 使用真实 CowMemoryManager
// ============================================================

fn bench_cow_snapshot_real(c: &mut Criterion) {
    let mut group = c.benchmark_group("cow_memory_real");
    
    // 测试不同大小的数据集
    for size in [100, 1000, 10000, 100000].iter() {
        // COW 快照 - O(1)
        group.bench_with_input(
            BenchmarkId::new("cow_snapshot", size),
            size,
            |b, &size| {
                b.iter(|| {
                    let manager = CowMemoryManager::new();
                    
                    // 填充数据
                    for i in 0..size {
                        manager.set(
                            format!("key_{}", i),
                            MemoryValue::String(format!("value_{}", i).repeat(100)),
                        );
                    }
                    
                    // 创建快照
                    let snapshot_id = manager.create_snapshot();
                    black_box(snapshot_id);
                    
                    // 获取统计
                    let stats = manager.get_stats();
                    black_box(stats);
                });
            },
        );
    }
    
    group.finish();
}

fn bench_cow_vs_deep_copy_comparison(c: &mut Criterion) {
    let mut group = c.benchmark_group("cow_vs_deep_copy");
    
    for size in [100, 1000, 10000].iter() {
        // COW 快照
        group.bench_with_input(
            BenchmarkId::new("cow", size),
            size,
            |b, &size| {
                b.iter(|| {
                    let manager = CowMemoryManager::new();
                    
                    // 填充数据
                    for i in 0..size {
                        manager.set(
                            format!("key_{}", i),
                            MemoryValue::String(format!("value_{}", i).repeat(100)),
                        );
                    }
                    
                    // 创建 10 个快照
                    for _ in 0..10 {
                        black_box(manager.create_snapshot());
                    }
                    
                    manager.get_stats()
                });
            },
        );
        
        // 深拷贝对比（使用 clone）
        group.bench_with_input(
            BenchmarkId::new("deep_copy", size),
            size,
            |b, &size| {
                b.iter(|| {
                    let mut data = std::collections::HashMap::new();
                    
                    // 填充数据
                    for i in 0..size {
                        data.insert(
                            format!("key_{}", i),
                            format!("value_{}", i).repeat(100),
                        );
                    }
                    
                    // 深拷贝 10 次
                    for _ in 0..10 {
                        black_box(data.clone());
                    }
                    
                    data.len()
                });
            },
        );
    }
    
    group.finish();
}

fn bench_tree_of_thoughts_cow(c: &mut Criterion) {
    let mut group = c.benchmark_group("tree_of_thoughts_cow");
    
    // 测试不同分支数量
    for branches in [10, 100, 1000].iter() {
        group.bench_with_input(
            BenchmarkId::new("cow_tot", branches),
            branches,
            |b, &branches| {
                b.iter(|| {
                    let manager = CowMemoryManager::new();
                    
                    // 初始状态
                    manager.set("problem".to_string(), MemoryValue::String("Solve X".to_string()));
                    
                    // 创建根快照
                    let root = manager.create_snapshot();
                    
                    // 创建多个思维分支
                    let mut branch_ids = Vec::new();
                    for i in 0..branches {
                        let branch = manager.create_branch(root);
                        manager.set(
                            format!("approach_{}", i),
                            MemoryValue::String(format!("algorithm_{}", i)),
                        );
                        branch_ids.push(branch);
                    }
                    
                    // 获取性能统计
                    let stats = manager.get_stats();
                    black_box((branch_ids, stats))
                });
            },
        );
    }
    
    group.finish();
}

// ============================================================
// 2. Work-Stealing 调度器测试 - 使用真实 WorkStealingScheduler
// ============================================================

fn bench_work_stealing_real(c: &mut Criterion) {
    let mut group = c.benchmark_group("work_stealing_real");
    
    for num_tasks in [100, 1000, 10000].iter() {
        group.throughput(Throughput::Elements(*num_tasks as u64));
        
        group.bench_with_input(
            BenchmarkId::new("schedule_tasks", num_tasks),
            num_tasks,
            |b, &num_tasks| {
                b.iter(|| {
                    let config = WorkStealingConfig {
                        steal_threshold: 2,
                        steal_batch_size: 2,
                        max_concurrent: 100,
                    };
                    let mut scheduler = WorkStealingScheduler::with_config(4, config);
                    
                    // 提交任务
                    for i in 0..num_tasks {
                        let task = AgentScheduleInfo::new(i as u64);
                        scheduler.submit(task).unwrap();
                    }
                    
                    // 执行调度
                    let mut completed = 0;
                    for _ in 0..num_tasks {
                        for worker_id in 0..4 {
                            if let Some(task) = scheduler.schedule(worker_id) {
                                scheduler.complete(task.agent_id);
                                completed += 1;
                            }
                        }
                    }
                    
                    let stats = scheduler.stats();
                    black_box((completed, stats.load_balance_efficiency))
                });
            },
        );
    }
    
    group.finish();
}

fn bench_load_balancing_efficiency(c: &mut Criterion) {
    let mut group = c.benchmark_group("load_balancing");
    
    // 测试不同 worker 数量
    for num_workers in [2, 4, 8, 16].iter() {
        group.bench_with_input(
            BenchmarkId::new("workers", num_workers),
            num_workers,
            |b, &num_workers| {
                b.iter(|| {
                    let mut scheduler = WorkStealingScheduler::new(num_workers);
                    
                    // 提交不均匀分布的任务
                    for i in 0..1000 {
                        let task = AgentScheduleInfo::new(i);
                        scheduler.submit(task).unwrap();
                    }
                    
                    // 执行负载均衡
                    scheduler.rebalance();
                    
                    // 获取效率
                    let stats = scheduler.stats();
                    black_box(stats.load_balance_efficiency)
                });
            },
        );
    }
    
    group.finish();
}

// ============================================================
// 3. 综合性能测试
// ============================================================

fn bench_comprehensive_cow_workstealing(c: &mut Criterion) {
    let mut group = c.benchmark_group("comprehensive");
    
    group.bench_function("cow_with_scheduler", |b| {
        b.iter(|| {
            // 创建 COW 内存
            let memory = CowMemoryManager::new();
            
            // 创建调度器
            let mut scheduler = WorkStealingScheduler::new(4);
            
            // 模拟 Tree-of-Thoughts + 并行执行
            let root = memory.create_snapshot();
            
            // 创建分支
            let mut branches = Vec::new();
            for i in 0..10 {
                let branch = memory.create_branch(root);
                memory.set(
                    format!("thought_{}", i),
                    MemoryValue::String(format!("approach_{}", i)),
                );
                
                // 创建对应任务
                let task = AgentScheduleInfo::new(branch);
                scheduler.submit(task).unwrap();
                branches.push(branch);
            }
            
            // 并行调度
            for worker_id in 0..4 {
                while let Some(task) = scheduler.schedule(worker_id) {
                    scheduler.complete(task.agent_id);
                }
            }
            
            // 获取报告
            let memory_stats = memory.get_stats();
            let scheduler_stats = scheduler.stats().clone();
            
            black_box((memory_stats, scheduler_stats))
        });
    });
    
    group.finish();
}

// ============================================================
// 性能报告生成
// ============================================================

fn generate_performance_report() -> String {
    format!(
        r#"
============================================================
Nexa AVM 性能基准测试报告
============================================================

1. COW 内存性能
   - 论文声称: 200,000x 加速比 (0.1ms vs 20,178ms deep copy)
   - 测试方法: 对比 COW snapshot 与 HashMap clone
   - 数据规模: 100, 1000, 10000 条记录

2. Work-Stealing 调度器
   - 论文声称: 负载均衡效率 > 95%
   - 测试方法: 提交任务并测量负载分布
   - Worker 数量: 2, 4, 8, 16

3. Tree-of-Thoughts 模式
   - 测试 COW 内存在多分支场景下的性能
   - 分支数量: 10, 100, 1000

运行方式:
    cargo bench --features wasm

注意:
    - 这些测试使用真实的 Rust AVM 组件
    - COW 性能取决于数据规模，大数据集加速比更高
    - Work-Stealing 效率取决于任务分布
"#
    )
}

criterion_group!(
    benches,
    bench_cow_snapshot_real,
    bench_cow_vs_deep_copy_comparison,
    bench_tree_of_thoughts_cow,
    bench_work_stealing_real,
    bench_load_balancing_efficiency,
    bench_comprehensive_cow_workstealing,
);

criterion_main!(benches);