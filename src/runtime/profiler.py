"""
Nexa 性能分析器 - Token 消耗、执行时间追踪

使用示例:
    from src.runtime.profiler import NexaProfiler
    
    profiler = NexaProfiler()
    profiler.start()
    
    # ... 运行 Agent ...
    
    stats = profiler.get_stats()
    print(f"总 Token: {stats['total_tokens']}")
    print(f"总时间: {stats['total_time_ms']}ms")
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import json


# ==================== 性能指标 ====================

@dataclass
class Metric:
    """性能指标"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AgentMetrics:
    """Agent 性能指标"""
    agent_name: str
    call_count: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "agent_name": self.agent_name,
            "call_count": self.call_count,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_time_ms": round(self.total_time_ms, 2),
            "avg_time_ms": round(self.avg_time_ms, 2),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(self.cache_hits / (self.cache_hits + self.cache_misses), 2) if (self.cache_hits + self.cache_misses) > 0 else 0,
            "errors": self.errors
        }


@dataclass
class FlowMetrics:
    """Flow 性能指标"""
    flow_name: str
    call_count: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    agent_calls: int = 0
    parallelism_avg: float = 1.0
    
    def to_dict(self) -> Dict:
        return {
            "flow_name": self.flow_name,
            "call_count": self.call_count,
            "total_time_ms": round(self.total_time_ms, 2),
            "avg_time_ms": round(self.avg_time_ms, 2),
            "agent_calls": self.agent_calls,
            "parallelism_avg": round(self.parallelism_avg, 2)
        }


# ==================== 性能分析器 ====================

class NexaProfiler:
    """
    Nexa 性能分析器
    
    功能:
    - Token 消耗追踪
    - 执行时间追踪
    - 缓存命中率统计
    - Agent/Flow 级别指标
    - 性能报告生成
    """
    
    def __init__(self):
        self.enabled = False
        self.start_time: Optional[float] = None
        
        # 指标存储
        self.agent_metrics: Dict[str, AgentMetrics] = {}
        self.flow_metrics: Dict[str, FlowMetrics] = {}
        self.raw_metrics: List[Metric] = []
        
        # 调用追踪
        self.current_flow: Optional[str] = None
        self.flow_stack: List[str] = []
        self.agent_in_flight: Dict[str, float] = {}  # agent_name -> start_time
        
        # 配置
        self.max_raw_metrics = 10000
        self.slow_threshold_ms = 1000  # 慢执行阈值
    
    # ==================== 生命周期 ====================
    
    def start(self):
        """开始分析"""
        self.enabled = True
        self.start_time = time.time()
    
    def stop(self):
        """停止分析"""
        self.enabled = False
    
    def reset(self):
        """重置所有指标"""
        self.agent_metrics.clear()
        self.flow_metrics.clear()
        self.raw_metrics.clear()
        self.flow_stack.clear()
        self.agent_in_flight.clear()
        self.start_time = time.time()
    
    # ==================== Agent 追踪 ====================
    
    def track_agent_start(self, agent_name: str, input_preview: str = ""):
        """追踪 Agent 开始执行"""
        if not self.enabled:
            return
        
        self.agent_in_flight[agent_name] = time.time()
        
        self._record_metric(
            "agent_start",
            1.0,
            "count",
            {"agent": agent_name, "input_preview": input_preview[:100]}
        )
        
        # 关联当前 Flow
        if self.current_flow:
            flow = self.flow_metrics.get(self.current_flow)
            if flow:
                flow.agent_calls += 1
    
    def track_agent_end(self, agent_name: str, success: bool = True,
                        prompt_tokens: int = 0, completion_tokens: int = 0,
                        cached: bool = False):
        """追踪 Agent 执行结束"""
        if not self.enabled:
            return
        
        start_time = self.agent_in_flight.pop(agent_name, time.time())
        elapsed_ms = (time.time() - start_time) * 1000
        
        # 更新 Agent 指标
        if agent_name not in self.agent_metrics:
            self.agent_metrics[agent_name] = AgentMetrics(agent_name=agent_name)
        
        metrics = self.agent_metrics[agent_name]
        metrics.call_count += 1
        metrics.total_time_ms += elapsed_ms
        metrics.avg_time_ms = metrics.total_time_ms / metrics.call_count
        metrics.total_tokens += prompt_tokens + completion_tokens
        metrics.prompt_tokens += prompt_tokens
        metrics.completion_tokens += completion_tokens
        
        if cached:
            metrics.cache_hits += 1
        else:
            metrics.cache_misses += 1
        
        if not success:
            metrics.errors += 1
        
        # 记录原始指标
        self._record_metric(
            "agent_end",
            elapsed_ms,
            "ms",
            {
                "agent": agent_name,
                "success": str(success),
                "tokens": str(prompt_tokens + completion_tokens),
                "cached": str(cached)
            }
        )
        
        # 检查慢执行
        if elapsed_ms > self.slow_threshold_ms:
            self._record_metric(
                "slow_execution",
                elapsed_ms,
                "ms",
                {"agent": agent_name, "type": "agent"}
            )
    
    # ==================== Flow 追踪 ====================
    
    def track_flow_start(self, flow_name: str):
        """追踪 Flow 开始"""
        if not self.enabled:
            return
        
        self.flow_stack.append(flow_name)
        self.current_flow = flow_name
        
        if flow_name not in self.flow_metrics:
            self.flow_metrics[flow_name] = FlowMetrics(flow_name=flow_name)
        
        self._record_metric(
            "flow_start",
            1.0,
            "count",
            {"flow": flow_name}
        )
    
    def track_flow_end(self, flow_name: str, parallelism: int = 1):
        """追踪 Flow 结束"""
        if not self.enabled:
            return
        
        metrics = self.flow_metrics.get(flow_name)
        if metrics:
            metrics.call_count += 1
            # 计算平均并行度
            metrics.parallelism_avg = (
                (metrics.parallelism_avg * (metrics.call_count - 1) + parallelism) 
                / metrics.call_count
            )
        
        if self.flow_stack and self.flow_stack[-1] == flow_name:
            self.flow_stack.pop()
        
        self.current_flow = self.flow_stack[-1] if self.flow_stack else None
        
        self._record_metric(
            "flow_end",
            1.0,
            "count",
            {"flow": flow_name}
        )
    
    # ==================== 工具追踪 ====================
    
    def track_tool_call(self, tool_name: str, success: bool, elapsed_ms: float):
        """追踪工具调用"""
        if not self.enabled:
            return
        
        self._record_metric(
            "tool_call",
            elapsed_ms,
            "ms",
            {"tool": tool_name, "success": str(success)}
        )
    
    # ==================== Token 追踪 ====================
    
    def track_tokens(self, source: str, prompt_tokens: int, completion_tokens: int):
        """追踪 Token 使用"""
        if not self.enabled:
            return
        
        self._record_metric(
            "tokens_used",
            prompt_tokens + completion_tokens,
            "tokens",
            {
                "source": source,
                "prompt": str(prompt_tokens),
                "completion": str(completion_tokens)
            }
        )
    
    # ==================== 指标记录 ====================
    
    def _record_metric(self, name: str, value: float, unit: str, tags: Dict = None):
        """记录原始指标"""
        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            tags=tags or {}
        )
        self.raw_metrics.append(metric)
        
        # 限制存储
        if len(self.raw_metrics) > self.max_raw_metrics:
            self.raw_metrics = self.raw_metrics[-self.max_raw_metrics:]
    
    def record_custom_metric(self, name: str, value: float, unit: str = "", tags: Dict = None):
        """记录自定义指标"""
        self._record_metric(name, value, unit, tags)
    
    # ==================== 统计报告 ====================
    
    def get_stats(self) -> Dict:
        """获取完整统计"""
        total_time = (time.time() - self.start_time) * 1000 if self.start_time else 0
        
        # 汇总 Token
        total_tokens = sum(m.total_tokens for m in self.agent_metrics.values())
        prompt_tokens = sum(m.prompt_tokens for m in self.agent_metrics.values())
        completion_tokens = sum(m.completion_tokens for m in self.agent_metrics.values())
        
        # 汇总缓存
        total_cache_hits = sum(m.cache_hits for m in self.agent_metrics.values())
        total_cache_misses = sum(m.cache_misses for m in self.agent_metrics.values())
        
        return {
            "enabled": self.enabled,
            "session_duration_ms": round(total_time, 2),
            "token_usage": {
                "total_tokens": total_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "tokens_per_second": round(total_tokens / (total_time / 1000), 2) if total_time > 0 else 0
            },
            "cache_performance": {
                "hits": total_cache_hits,
                "misses": total_cache_misses,
                "hit_rate": round(total_cache_hits / (total_cache_hits + total_cache_misses), 2) if (total_cache_hits + total_cache_misses) > 0 else 0
            },
            "agent_count": len(self.agent_metrics),
            "flow_count": len(self.flow_metrics),
            "total_agent_calls": sum(m.call_count for m in self.agent_metrics.values()),
            "total_flow_calls": sum(m.call_count for m in self.flow_metrics.values()),
            "slow_executions": len([m for m in self.raw_metrics if m.name == "slow_execution"]),
            "errors": sum(m.errors for m in self.agent_metrics.values())
        }
    
    def get_agent_stats(self) -> List[Dict]:
        """获取所有 Agent 统计"""
        return [m.to_dict() for m in sorted(
            self.agent_metrics.values(),
            key=lambda x: x.total_time_ms,
            reverse=True
        )]
    
    def get_flow_stats(self) -> List[Dict]:
        """获取所有 Flow 统计"""
        return [m.to_dict() for m in self.flow_metrics.values()]
    
    def get_top_agents(self, by: str = "total_tokens", limit: int = 10) -> List[Dict]:
        """
        获取 Top Agent
        
        Args:
            by: 排序字段 (total_tokens, total_time_ms, call_count)
            limit: 返回数量
        """
        sorted_agents = sorted(
            self.agent_metrics.values(),
            key=lambda x: getattr(x, by, 0),
            reverse=True
        )
        return [m.to_dict() for m in sorted_agents[:limit]]
    
    def get_slow_operations(self, threshold_ms: float = None) -> List[Dict]:
        """获取慢操作列表"""
        threshold = threshold_ms or self.slow_threshold_ms
        slow_metrics = [
            m for m in self.raw_metrics
            if m.name in ("agent_end", "tool_call") and m.value > threshold
        ]
        
        return [
            {
                "type": m.name,
                "value": round(m.value, 2),
                "unit": m.unit,
                "timestamp": m.timestamp.isoformat(),
                "details": m.tags
            }
            for m in sorted(slow_metrics, key=lambda x: x.value, reverse=True)
        ]
    
    def export_report(self, format: str = "json") -> str:
        """
        导出性能报告
        
        Args:
            format: 格式 (json, markdown)
        """
        stats = self.get_stats()
        
        if format == "json":
            report = {
                "summary": stats,
                "agents": self.get_agent_stats(),
                "flows": self.get_flow_stats(),
                "slow_operations": self.get_slow_operations()
            }
            return json.dumps(report, indent=2, ensure_ascii=False)
        
        elif format == "markdown":
            lines = [
                "# Nexa 性能分析报告",
                "",
                "## 📊 概览",
                "",
                f"- **会话时长**: {stats['session_duration_ms']:.0f}ms",
                f"- **总 Token**: {stats['token_usage']['total_tokens']:,}",
                f"- **Token/秒**: {stats['token_usage']['tokens_per_second']}",
                f"- **缓存命中率**: {stats['cache_performance']['hit_rate']:.0%}",
                f"- **Agent 调用**: {stats['total_agent_calls']}",
                f"- **错误数**: {stats['errors']}",
                "",
                "## 🤖 Agent 性能",
                "",
                "| Agent | 调用次数 | 总Token | 平均耗时 | 缓存命中 |",
                "|-------|---------|---------|---------|---------|",
            ]
            
            for agent in self.get_agent_stats()[:10]:
                lines.append(
                    f"| {agent['agent_name']} | {agent['call_count']} | "
                    f"{agent['total_tokens']} | {agent['avg_time_ms']:.0f}ms | "
                    f"{agent['cache_hit_rate']:.0%} |"
                )
            
            lines.extend([
                "",
                "## ⚠️ 慢操作",
                ""
            ])
            
            for op in self.get_slow_operations()[:5]:
                lines.append(
                    f"- **{op['type']}**: {op['value']:.0f}ms ({op['details']})"
                )
            
            return "\n".join(lines)
        
        return ""
    
    # ==================== 实时监控 ====================
    
    def get_realtime_stats(self) -> Dict:
        """获取实时统计 (用于仪表板)"""
        return {
            "timestamp": datetime.now().isoformat(),
            "active_agents": len(self.agent_in_flight),
            "current_flow": self.current_flow,
            **self.get_stats()
        }


# ==================== 全局分析器 ====================

_global_profiler: Optional[NexaProfiler] = None


def get_profiler() -> NexaProfiler:
    """获取全局分析器实例"""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = NexaProfiler()
    return _global_profiler


def init_profiler() -> NexaProfiler:
    """初始化新的分析器"""
    global _global_profiler
    _global_profiler = NexaProfiler()
    return _global_profiler


def start_profiling():
    """开始全局分析"""
    get_profiler().start()


def stop_profiling():
    """停止全局分析"""
    get_profiler().stop()


def get_profiling_stats() -> Dict:
    """获取全局分析统计"""
    return get_profiler().get_stats()