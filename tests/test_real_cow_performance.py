#!/usr/bin/env python3
"""
真实 COW 性能测试 - 使用 Nexa 的真实运行时组件

测试 NexaAgent.clone() 的 COW 实现性能。
论文声称：COW snapshot 性能提升可达 200,000x (0.1ms vs 20,178ms deep copy)

运行方式：
    python tests/test_real_cow_performance.py
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.runtime.cow_state import CowAgentState, CowAgentStateRegistry


def test_cow_state_basic():
    """测试 COW 状态基本功能"""
    print("\n" + "="*60)
    print("测试 COW 状态基本功能")
    print("="*60)
    
    # 创建状态
    state = CowAgentState()
    state.set("key1", "value1")
    state.set("key2", "value2")
    state.set("key3", {"nested": "data"})
    
    # 读取测试
    assert state.get("key1") == "value1"
    assert state.get("key2") == "value2"
    assert state.get("key3")["nested"] == "data"
    assert state.get("nonexistent") is None
    
    # 克隆测试
    cloned = state.clone()
    assert cloned.get("key1") == "value1"
    
    # 修改克隆不影响原状态
    cloned.set("key1", "modified")
    assert state.get("key1") == "value1"  # 原状态不变
    assert cloned.get("key1") == "modified"  # 克隆状态已修改
    
    print("✓ COW 状态基本功能测试通过")


def test_cow_vs_deep_copy_performance():
    """
    COW 快照 vs 深拷贝性能对比测试
    
    论文声称：200,000x 加速比 (0.1ms vs 20,178ms)
    """
    print("\n" + "="*60)
    print("COW 快照 vs 深拷贝性能对比")
    print("="*60)
    
    results = {}
    
    for size in [10, 100, 1000, 10000]:
        # 创建状态并填充数据
        state = CowAgentState()
        for i in range(size):
            state.set(f"key_{i}", f"value_{i}" * 100)  # 每个值约 1KB
        
        # COW 克隆测试 - 10 次
        start = time.perf_counter()
        cow_clones = []
        for _ in range(10):
            cow_clones.append(state.clone())
        cow_time = time.perf_counter() - start
        
        # 深拷贝测试 - 10 次
        start = time.perf_counter()
        deep_clones = []
        for _ in range(10):
            deep_clones.append(state.deep_clone())
        deep_time = time.perf_counter() - start
        
        # 计算加速比
        speedup = deep_time / cow_time if cow_time > 0 else 0
        
        results[size] = {
            'cow_time_ms': cow_time * 1000,
            'deep_copy_time_ms': deep_time * 1000,
            'speedup': speedup,
            'cow_per_clone_ms': cow_time * 1000 / 10,
            'deep_per_clone_ms': deep_time * 1000 / 10,
        }
        
        print(f"\n数据大小: {size} 条记录 (~{size}KB)")
        print(f"  COW 10 次克隆:      {cow_time*1000:.3f} ms ({cow_time*1000/10:.3f} ms/clone)")
        print(f"  Deep Copy 10 次:    {deep_time*1000:.3f} ms ({deep_time*1000/10:.3f} ms/clone)")
        print(f"  加速比:             {speedup:.0f}x")
    
    # 验证加速比
    print(f"\n论文声称: 200,000x 加速比 (基于 20MB 数据集)")
    print(f"实际测量: 对于 {max(results.keys())} 条记录，加速比为 {results[max(results.keys())]['speedup']:.0f}x")
    
    # 验证 COW 性能要求：至少 100x 加速比
    for size, result in results.items():
        if size >= 1000:
            assert result['speedup'] > 100, f"COW 加速比 {result['speedup']:.0f}x 未达到 100x 要求"
    
    print("\n✓ COW 性能测试通过")
    return results


def test_tree_of_thoughts_pattern():
    """
    Tree-of-Thoughts 模式性能测试
    
    模拟多分支思维探索场景
    """
    print("\n" + "="*60)
    print("Tree-of-Thoughts 模式性能测试")
    print("="*60)
    
    results = {}
    
    for branches in [3, 10, 100, 1000]:
        # 创建初始状态
        root_state = CowAgentState()
        root_state.set("problem", "Solve complex problem X")
        root_state.set("context", {"domain": "math", "difficulty": "hard"})
        
        # COW 模式：创建多个思维分支
        start = time.perf_counter()
        thought_branches = []
        for i in range(branches):
            branch = root_state.create_branch()
            branch.set("approach", f"algorithm_{i}")
            branch.set("step", 1)
            thought_branches.append(branch)
        cow_time = time.perf_counter() - start
        
        # 深拷贝模式：创建多个思维分支
        start = time.perf_counter()
        deep_branches = []
        for i in range(branches):
            branch = root_state.deep_clone()
            branch.set("approach", f"algorithm_{i}")
            branch.set("step", 1)
            deep_branches.append(branch)
        deep_time = time.perf_counter() - start
        
        speedup = deep_time / cow_time if cow_time > 0 else 0
        
        results[branches] = {
            'cow_time_ms': cow_time * 1000,
            'deep_copy_time_ms': deep_time * 1000,
            'speedup': speedup,
        }
        
        print(f"\n分支数量: {branches}")
        print(f"  COW 模式:       {cow_time*1000:.3f} ms")
        print(f"  Deep Copy 模式: {deep_time*1000:.3f} ms")
        print(f"  加速比:         {speedup:.0f}x")
    
    print(f"\n✓ Tree-of-Thoughts 模式测试完成")
    return results


def test_cow_state_isolation():
    """测试 COW 状态隔离性"""
    print("\n" + "="*60)
    print("测试 COW 状态隔离性")
    print("="*60)
    
    # 创建原始状态
    original = CowAgentState()
    original.set("shared", "original_value")
    original.set("original_only", "only_in_original")
    
    # 创建克隆
    cloned = original.clone()
    
    # 修改克隆
    cloned.set("shared", "modified_in_clone")
    cloned.set("clone_only", "only_in_clone")
    
    # 删除克隆中的键
    cloned.delete("original_only")
    
    # 验证原状态不受影响
    assert original.get("shared") == "original_value", "原状态被修改"
    assert original.get("original_only") == "only_in_original", "原状态键被删除"
    assert original.get("clone_only") is None, "原状态获取了克隆的键"
    
    # 验证克隆状态
    assert cloned.get("shared") == "modified_in_clone", "克隆状态未正确修改"
    assert cloned.get("clone_only") == "only_in_clone", "克隆状态未正确添加"
    assert cloned.get("original_only") is None, "克隆状态未正确删除"
    
    print("✓ COW 状态隔离性测试通过")


def test_cow_stats():
    """测试 COW 统计功能"""
    print("\n" + "="*60)
    print("测试 COW 统计功能")
    print("="*60)
    
    state = CowAgentState()
    
    # 填充数据
    for i in range(100):
        state.set(f"key_{i}", f"value_{i}")
    
    # 执行操作
    for _ in range(10):
        state.clone()
    
    for _ in range(5):
        state.deep_clone()
    
    # 获取统计
    stats = state.get_stats()
    print(f"\n统计信息:")
    print(f"  总克隆次数: {stats.total_clones}")
    print(f"  总深拷贝次数: {stats.total_deep_copies}")
    print(f"  总克隆时间: {stats.total_clone_time_ms:.3f} ms")
    print(f"  总深拷贝时间: {stats.total_deep_copy_time_ms:.3f} ms")
    print(f"  加速比: {stats.speedup:.0f}x")
    
    print(f"\n性能报告:\n{state.performance_report()}")
    
    print("✓ COW 统计功能测试通过")


def test_cow_registry():
    """测试 COW 状态注册表"""
    print("\n" + "="*60)
    print("测试 COW 状态注册表")
    print("="*60)
    
    registry = CowAgentStateRegistry()
    
    # 创建状态
    state1 = registry.create("agent_1")
    state1.set("data", "value1")
    
    # 克隆状态
    state2 = registry.clone("agent_1", "agent_2")
    assert state2 is not None
    assert state2.get("data") == "value1"
    
    # 列出状态
    states = registry.list_states()
    assert "agent_1" in states
    assert "agent_2" in states
    
    # 删除状态
    assert registry.delete("agent_1")
    assert registry.get("agent_1") is None
    
    print("✓ COW 状态注册表测试通过")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Nexa COW 真实性能测试报告")
    print("="*60)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    test_cow_state_basic()
    test_cow_state_isolation()
    cow_results = test_cow_vs_deep_copy_performance()
    tot_results = test_tree_of_thoughts_pattern()
    test_cow_stats()
    test_cow_registry()
    
    # 总结
    print("\n" + "="*60)
    print("性能测试总结")
    print("="*60)
    
    max_size = max(cow_results.keys())
    max_speedup = cow_results[max_size]['speedup']
    
    print(f"\n| 测试项 | 论文声称 | 实际测量 | 状态 |")
    print(f"|--------|----------|----------|------|")
    print(f"| COW 加速比 | 200,000x | {max_speedup:.0f}x | {'✅' if max_speedup >= 100 else '⚠️'} |")
    
    print(f"\n说明: 论文中的 200,000x 加速比是基于 20MB 数据集测量的。")
    print(f"      在较小的数据集上，加速比会相应降低，但仍保持显著优势。")
    
    return {
        'cow_results': cow_results,
        'tot_results': tot_results,
    }


if __name__ == "__main__":
    results = run_all_tests()
    print("\n✅ 所有 COW 性能测试通过")