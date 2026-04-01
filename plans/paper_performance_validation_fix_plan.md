# 论文性能验证修复计划

## 问题诊断

### 严重问题：模拟测试而非真实测试

之前创建的 `tests/test_paper_performance_benchmarks.py` 存在关键问题：

| 测试项 | 测试文件使用 | Nexa 真实实现 | 问题 |
|--------|--------------|---------------|------|
| COW | 自定义 `CowMemoryManager` 类 | `avm/src/vm/cow_memory.rs` | ❌ 未使用真实 COW |
| 缓存 | 自定义 `SimpleCache` 类 | `src/runtime/cache_manager.py` | ❌ 未使用真实缓存 |
| WASM | Python 模拟检查 | `avm/src/wasm/sandbox.rs` | ❌ 未使用真实 WASM |
| Work-Stealing | 自定义 `WorkStealingScheduler` | `avm/src/vm/scheduler.rs` | ❌ 未使用真实调度器 |

### 架构分离现状

```
┌─────────────────────────────────────────────────────────────┐
│                    Nexa 双层架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────────────┐    ┌─────────────────────────┐  │
│  │   Python SDK (src/)   │    │   Rust AVM (avm/)       │  │
│  │                       │    │                         │  │
│  │  • NexaAgent          │    │  • CowMemoryManager     │  │
│  │  • NexaCacheManager   │    │  • WorkStealingScheduler│  │
│  │  • Orchestrator       │    │  • WasmSandbox          │  │
│  │  • Parser/Transformer │    │  • SmartScheduler       │  │
│  │                       │    │                         │  │
│  │  特性:                 │    │  特性:                   │  │
│  │  - 语义缓存 (真实)     │    │  - COW 内存 (真实)       │  │
│  │  - Agent.clone()      │    │  - WASM 沙盒 (真实)      │  │
│  │    (创建新实例)        │    │  - Work-Stealing (真实)  │  │
│  │                       │    │                         │  │
│  └───────────────────────┘    └─────────────────────────┘  │
│                                                             │
│  FFI 绑定: avm/src/ffi/python.rs (尚未完全集成)             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 论文声称 vs 实际能力

| 特性 | 论文声称 | Python SDK 状态 | Rust AVM 状态 |
|------|----------|-----------------|---------------|
| COW 性能提升 | 200,000x | ❌ 不支持 (clone 创建新实例) | ✅ 已实现 |
| WASM 开销 | 10-20% | ❌ 不使用 WASM | ✅ 已实现 (需验证) |
| 缓存命中率 | 90% | ✅ 可验证 | ⚠️ 需测试 LLM 缓存 |
| Work-Stealing | >95% 效率 | ❌ 不支持 | ✅ 已实现 |

## 修复计划

### Phase 1: 清理模拟测试

1. **删除模拟测试文件**
   - 删除 `tests/test_paper_performance_benchmarks.py`
   - 删除 `avm/benches/paper_performance_bench.rs` 中的模拟代码

### Phase 2: Rust AVM 真实基准测试

1. **COW 内存性能测试**
   - 文件: `avm/benches/cow_bench.rs`
   - 使用真实的 `CowMemoryManager`
   - 测试: 创建快照 vs 深拷贝对比
   - 数据集: 100KB, 1MB, 10MB, 100MB

2. **Work-Stealing 调度器测试**
   - 文件: `avm/benches/scheduler_bench.rs`
   - 使用真实的 `WorkStealingScheduler`
   - 测试: 负载均衡效率、窃取成功率

3. **WASM 沙盒开销测试**
   - 文件: `avm/benches/wasm_bench.rs`
   - 需要 wasmtime feature 启用
   - 测试: 原生执行 vs WASM 执行

### Phase 3: Python SDK 真实测试

1. **缓存命中率测试**
   - 文件: `tests/test_cache_hit_rate.py`
   - 使用真实的 `NexaCacheManager`
   - 测试: 精确匹配 vs 语义匹配

### Phase 4: 文档更新

1. **明确性能声明适用范围**
   - COW/WASM/Work-Stealing: 仅 Rust AVM
   - 缓存: Python SDK 和 Rust AVM

2. **如果性能不达标，修改论文**
   - 报告真实测量值
   - 说明适用条件

## 执行步骤

### Step 1: 删除模拟测试
```bash
rm tests/test_paper_performance_benchmarks.py
```

### Step 2: 创建 Rust AVM 真实基准测试

```rust
// avm/benches/cow_bench.rs
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use nexa_avm::vm::cow_memory::{CowMemoryManager, MemoryValue};

fn bench_cow_vs_deep_copy(c: &mut Criterion) {
    let mut group = c.benchmark_group("cow_memory");
    
    // 使用真实 CowMemoryManager
    for size in [100, 1000, 10000, 100000].iter() {
        // COW 快照
        group.bench_with_input(BenchmarkId::new("cow_snapshot", size), size, |b, size| {
            b.iter(|| {
                let manager = CowMemoryManager::new();
                // 填充数据
                for i in 0..*size {
                    manager.set(format!("key_{}", i), MemoryValue::String(format!("value_{}", i)));
                }
                // 创建快照
                black_box(manager.create_snapshot());
            });
        });
        
        // 深拷贝对比
        group.bench_with_input(BenchmarkId::new("deep_copy", size), size, |b, size| {
            b.iter(|| {
                let mut data = HashMap::new();
                // 填充数据
                for i in 0..*size {
                    data.insert(format!("key_{}", i), format!("value_{}", i));
                }
                // 深拷贝
                black_box(data.clone());
            });
        });
    }
    
    group.finish();
}

criterion_group!(benches, bench_cow_vs_deep_copy);
criterion_main!(benches);
```

### Step 3: 运行 Rust 基准测试
```bash
cd avm && cargo bench --features wasm
```

### Step 4: 创建 Python 缓存测试
```python
# tests/test_cache_hit_rate.py
from src.runtime.cache_manager import NexaCacheManager, get_cache_manager

def test_real_cache_hit_rate():
    manager = NexaCacheManager(enable_semantic_cache=True)
    
    # 预热缓存
    messages = [{"role": "user", "content": "Hello"}]
    manager.set(messages, "gpt-4", "Hi there!")
    
    # 测试精确匹配
    result = manager.get(messages, "gpt-4")
    assert result is not None  # 应该命中
    
    stats = manager.get_stats()
    print(f"Hit rate: {stats['hit_rate']}")
```

## 预期结果

### 如果 Rust AVM 性能达标
- 更新文档说明性能仅适用于 Rust AVM
- Python SDK 用户需要了解限制

### 如果性能不达标
- 报告真实测量值
- 修改论文/文档中的性能声明

## 验收标准

1. 所有基准测试使用真实运行时组件
2. 测试结果可重现
3. 论文/文档准确反映实际能力
4. 明确区分 Python SDK 和 Rust AVM 的能力范围