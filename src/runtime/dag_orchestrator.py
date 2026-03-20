"""
Nexa DAG Orchestrator - 复杂拓扑DAG支持模块
支持分叉(Fan-out)、合流(Fan-in)、条件分支、并行执行等高阶数据流转编排
"""

import concurrent.futures
from typing import List, Dict, Any, Callable, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
from .agent import NexaAgent


class DAGNodeType(Enum):
    """DAG节点类型"""
    AGENT = "agent"
    FORK = "fork"          # 分叉节点 - 一输入多输出
    MERGE = "merge"        # 合流节点 - 多输入一输出
    CONDITION = "condition"  # 条件分支节点
    PARALLEL = "parallel"  # 并行执行节点
    TRANSFORM = "transform"  # 数据转换节点


@dataclass
class DAGNode:
    """DAG节点基类"""
    id: str
    node_type: DAGNodeType
    agent: Optional[NexaAgent] = None
    transform_fn: Optional[Callable] = None
    condition_fn: Optional[Callable] = None
    next_nodes: List['DAGNode'] = field(default_factory=list)
    merge_strategy: str = "concat"  # concat, first, last, vote
    
    def execute(self, input_data: Any, context: Dict = None) -> Any:
        """执行节点逻辑"""
        context = context or {}
        
        if self.node_type == DAGNodeType.AGENT and self.agent:
            return self.agent.run(str(input_data))
        
        elif self.node_type == DAGNodeType.TRANSFORM and self.transform_fn:
            return self.transform_fn(input_data, context)
        
        elif self.node_type == DAGNodeType.CONDITION and self.condition_fn:
            if self.condition_fn(input_data, context):
                return self._execute_next(input_data, context)
            return None
        
        return input_data
    
    def _execute_next(self, input_data: Any, context: Dict) -> Any:
        """执行下游节点"""
        if not self.next_nodes:
            return input_data
        if len(self.next_nodes) == 1:
            return self.next_nodes[0].execute(input_data, context)
        # 多下游节点时返回列表
        return [node.execute(input_data, context) for node in self.next_nodes]


@dataclass
class ForkNode(DAGNode):
    """分叉节点 - 将数据分发到多个下游节点"""
    def __init__(self, id: str, fanout_strategy: str = "broadcast"):
        super().__init__(id, DAGNodeType.FORK)
        self.fanout_strategy = fanout_strategy  # broadcast, round_robin, hash
    
    def execute(self, input_data: Any, context: Dict = None) -> List[Any]:
        """分叉执行 - 并行分发到所有下游节点"""
        context = context or {}
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.next_nodes)) as executor:
            futures = {
                executor.submit(node.execute, input_data, context): node
                for node in self.next_nodes
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(f"Error in {futures[future].id}: {e}")
        
        return results


@dataclass
class MergeNode(DAGNode):
    """合流节点 - 将多个上游节点的输出合并"""
    def __init__(self, id: str, merge_strategy: str = "concat", vote_threshold: float = 0.5):
        super().__init__(id, DAGNodeType.MERGE)
        self.merge_strategy = merge_strategy
        self.vote_threshold = vote_threshold
        self.pending_inputs: List[Any] = []
        self.expected_inputs: int = 0
    
    def collect(self, input_data: Any) -> bool:
        """收集输入，返回是否已收集完毕"""
        self.pending_inputs.append(input_data)
        return len(self.pending_inputs) >= self.expected_inputs
    
    def execute(self, inputs: List[Any], context: Dict = None) -> Any:
        """执行合流逻辑"""
        context = context or {}
        
        if self.merge_strategy == "concat":
            return self._merge_concat(inputs)
        elif self.merge_strategy == "first":
            return inputs[0] if inputs else None
        elif self.merge_strategy == "last":
            return inputs[-1] if inputs else None
        elif self.merge_strategy == "vote":
            return self._merge_vote(inputs)
        elif self.merge_strategy == "consensus":
            return self._merge_consensus(inputs, context)
        elif self.merge_strategy == "summarize":
            return self._merge_summarize(inputs, context)
        
        return inputs
    
    def _merge_concat(self, inputs: List[Any]) -> str:
        """连接所有输入"""
        return "\n---\n".join([str(inp) for inp in inputs if inp])
    
    def _merge_vote(self, inputs: List[Any]) -> Any:
        """投票选择最常见的输出"""
        from collections import Counter
        str_inputs = [str(inp) for inp in inputs]
        counter = Counter(str_inputs)
        most_common = counter.most_common(1)
        if most_common:
            threshold = len(inputs) * self.vote_threshold
            if most_common[0][1] >= threshold:
                return most_common[0][0]
        return str_inputs[0] if str_inputs else None
    
    def _merge_consensus(self, inputs: List[Any], context: Dict) -> str:
        """基于Agent的共识合并"""
        # 使用轻量模型生成共识总结
        return f"Consensus of {len(inputs)} inputs: " + self._merge_concat(inputs)
    
    def _merge_summarize(self, inputs: List[Any], context: Dict) -> str:
        """智能摘要合并"""
        return f"Summary of {len(inputs)} outputs:\n" + self._merge_concat(inputs)


class DAGExecutor:
    """DAG执行器 - 管理整个DAG的执行流程"""
    
    def __init__(self, entry_node: DAGNode):
        self.entry_node = entry_node
        self.execution_context: Dict[str, Any] = {}
        self.node_results: Dict[str, Any] = {}
    
    def run(self, initial_input: Any) -> Any:
        """执行整个DAG"""
        return self._execute_node(self.entry_node, initial_input)
    
    def _execute_node(self, node: DAGNode, input_data: Any) -> Any:
        """递归执行节点"""
        result = node.execute(input_data, self.execution_context)
        self.node_results[node.id] = result
        
        if node.next_nodes:
            if isinstance(result, list) and node.node_type == DAGNodeType.FORK:
                # 分叉结果已收集，每个下游节点收一个
                for i, next_node in enumerate(node.next_nodes):
                    if i < len(result):
                        self._execute_node(next_node, result[i])
            elif len(node.next_nodes) == 1:
                return self._execute_node(node.next_nodes[0], result)
            else:
                # 多下游节点，并行执行
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [
                        executor.submit(self._execute_node, n, result)
                        for n in node.next_nodes
                    ]
                    results = [f.result() for f in futures]
                return results
        
        return result


def dag_fanout(input_data: Any, agents: List[NexaAgent]) -> List[str]:
    """
    DAG分叉执行 - 将同一输入并行发送到多个Agent
    
    用法示例:
    result = dag_fanout(user_query, [Researcher, Analyst, Writer])
    # result 为三个Agent输出的列表
    """
    print(f"\n[DAG Fan-out] Distributing to {len(agents)} agents...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents)) as executor:
        futures = {executor.submit(agent.run, str(input_data)): agent for agent in agents}
        results = []
        
        for future in concurrent.futures.as_completed(futures):
            agent = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"  ✓ {agent.name}: {result[:100]}...")
            except Exception as e:
                results.append(f"Error from {agent.name}: {e}")
                print(f"  ✗ {agent.name}: {e}")
    
    return results


def dag_merge(inputs: List[Any], strategy: str = "concat", merge_agent: NexaAgent = None) -> str:
    """
    DAG合流执行 - 将多个输入合并为单一输出
    
    支持的合并策略:
    - concat: 简单连接
    - first: 取第一个
    - last: 取最后一个
    - vote: 投票选择
    - consensus: 基于Agent的共识
    - summarize: 智能摘要
    """
    print(f"\n[DAG Merge] Merging {len(inputs)} inputs with strategy: {strategy}")
    
    if strategy == "concat":
        return "\n---\n".join([str(inp) for inp in inputs if inp])
    
    elif strategy == "first":
        return str(inputs[0]) if inputs else ""
    
    elif strategy == "last":
        return str(inputs[-1]) if inputs else ""
    
    elif strategy == "vote":
        from collections import Counter
        str_inputs = [str(inp) for inp in inputs]
        counter = Counter(str_inputs)
        most_common = counter.most_common(1)
        return most_common[0][0] if most_common else ""
    
    elif strategy in ("consensus", "summarize") and merge_agent:
        merge_prompt = f"Please synthesize the following {len(inputs)} perspectives into a coherent response:\n\n"
        merge_prompt += "\n---\n".join([str(inp) for inp in inputs if inp])
        return merge_agent.run(merge_prompt)
    
    return str(inputs)


def dag_branch(input_data: Any, condition_fn: Callable, true_agent: NexaAgent, false_agent: NexaAgent = None) -> str:
    """
    DAG条件分支执行
    
    用法示例:
    result = dag_branch(query, lambda x: "紧急" in x, UrgentBot, NormalBot)
    """
    condition_result = condition_fn(input_data)
    print(f"\n[DAG Branch] Condition evaluated to: {condition_result}")
    
    if condition_result:
        return true_agent.run(str(input_data))
    elif false_agent:
        return false_agent.run(str(input_data))
    
    return ""


def dag_parallel_map(input_data: Any, agents: List[NexaAgent], reducer: str = "concat") -> str:
    """
    DAG并行映射 - 每个Agent处理输入的不同部分
    """
    if isinstance(input_data, str):
        # 简单分割
        parts = input_data.split("\n\n")
    elif isinstance(input_data, list):
        parts = input_data
    else:
        parts = [input_data]
    
    # 分配任务
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents)) as executor:
        futures = []
        for i, part in enumerate(parts):
            agent = agents[i % len(agents)]
            futures.append(executor.submit(agent.run, str(part)))
        
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    
    return dag_merge(results, strategy=reducer)


class SmartRouter:
    """
    智能路由器 - 基于语义分析动态选择执行路径
    """
    
    def __init__(self, routes: Dict[str, NexaAgent], default_agent: NexaAgent = None):
        self.routes = routes  # {intent_pattern: agent}
        self.default_agent = default_agent
    
    def route(self, input_data: str) -> NexaAgent:
        """根据输入选择最合适的Agent"""
        # 简单关键词匹配（可扩展为语义匹配）
        for pattern, agent in self.routes.items():
            if pattern.lower() in input_data.lower():
                print(f"[SmartRouter] Matched pattern '{pattern}' -> {agent.name}")
                return agent
        
        if self.default_agent:
            print(f"[SmartRouter] No match, using default -> {self.default_agent.name}")
            return self.default_agent
        
        raise ValueError(f"No suitable agent found for input: {input_data[:50]}...")
    
    def run(self, input_data: str) -> str:
        """执行智能路由"""
        agent = self.route(input_data)
        return agent.run(input_data)


# 导出便捷函数
__all__ = [
    'DAGNode', 'DAGNodeType', 'ForkNode', 'MergeNode', 'DAGExecutor',
    'dag_fanout', 'dag_merge', 'dag_branch', 'dag_parallel_map', 'SmartRouter'
]