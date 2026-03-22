"""
Nexa 调试器 - 断点、变量查看、单步执行

使用示例:
    from src.runtime.debugger import NexaDebugger
    
    debugger = NexaDebugger()
    debugger.set_breakpoint("agent", "ChatBot")
    debugger.set_breakpoint("flow", "main")
    
    result = debugger.run_script("script.nx")
"""

import os
import sys
import io
import contextlib
import importlib.util
import traceback
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# ==================== 断点类型 ====================

class BreakpointType(Enum):
    """断点类型"""
    AGENT = "agent"          # Agent 执行前
    TOOL = "tool"            # Tool 执行前
    FLOW = "flow"            # Flow 进入时
    LINE = "line"            # 特定行
    SEMANTIC = "semantic"    # 语义条件判断


@dataclass
class Breakpoint:
    """断点定义"""
    bp_type: BreakpointType
    target: str              # 目标名称 (agent名、tool名、flow名等)
    condition: Optional[str] = None  # 条件表达式
    enabled: bool = True
    hit_count: int = 0
    
    def should_break(self, context: Dict) -> bool:
        """判断是否应该中断"""
        if not self.enabled:
            return False
        
        if self.condition:
            try:
                return eval(self.condition, {}, context)
            except:
                return False
        return True


# ==================== 调试事件 ====================

@dataclass
class DebugEvent:
    """调试事件"""
    event_type: str
    timestamp: datetime
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    flow_name: Optional[str] = None
    message: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None


# ==================== 调试器状态 ====================

class DebuggerState(Enum):
    """调试器状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STEPPING = "stepping"
    STOPPED = "stopped"


# ==================== 变量监视 ====================

@dataclass
class Watch:
    """变量监视"""
    name: str
    expression: str
    value: Any = None
    type_name: str = ""
    last_updated: datetime = None


# ==================== 主调试器 ====================

class NexaDebugger:
    """
    Nexa 调试器
    
    功能:
    - 设置断点 (Agent、Tool、Flow、行号)
    - 单步执行
    - 变量监视
    - 调用栈追踪
    - 事件日志
    """
    
    def __init__(self):
        self.breakpoints: List[Breakpoint] = []
        self.watches: List[Watch] = []
        self.state = DebuggerState.IDLE
        self.events: List[DebugEvent] = []
        self.call_stack: List[str] = []
        self.current_variables: Dict[str, Any] = {}
        self.max_events = 1000
        
        # 回调函数
        self._on_breakpoint: Optional[Callable] = None
        self._on_step: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
    
    # ==================== 断点管理 ====================
    
    def set_breakpoint(self, bp_type: str, target: str, condition: str = None) -> Breakpoint:
        """
        设置断点
        
        Args:
            bp_type: 断点类型 (agent, tool, flow, line, semantic)
            target: 目标名称
            condition: 可选条件
            
        Returns:
            Breakpoint: 创建的断点
        """
        bp = Breakpoint(
            bp_type=BreakpointType(bp_type.lower()),
            target=target,
            condition=condition
        )
        self.breakpoints.append(bp)
        self._log_event("breakpoint_set", message=f"设置断点: {bp_type} '{target}'")
        return bp
    
    def remove_breakpoint(self, bp_type: str, target: str) -> bool:
        """移除断点"""
        for i, bp in enumerate(self.breakpoints):
            if bp.bp_type.value == bp_type.lower() and bp.target == target:
                del self.breakpoints[i]
                self._log_event("breakpoint_removed", message=f"移除断点: {bp_type} '{target}'")
                return True
        return False
    
    def clear_breakpoints(self):
        """清空所有断点"""
        self.breakpoints.clear()
        self._log_event("breakpoints_cleared", message="清空所有断点")
    
    def enable_breakpoint(self, bp_type: str, target: str, enabled: bool = True):
        """启用/禁用断点"""
        for bp in self.breakpoints:
            if bp.bp_type.value == bp_type.lower() and bp.target == target:
                bp.enabled = enabled
    
    def list_breakpoints(self) -> List[Dict]:
        """列出所有断点"""
        return [
            {
                "type": bp.bp_type.value,
                "target": bp.target,
                "condition": bp.condition,
                "enabled": bp.enabled,
                "hit_count": bp.hit_count
            }
            for bp in self.breakpoints
        ]
    
    # ==================== 变量监视 ====================
    
    def add_watch(self, name: str, expression: str) -> Watch:
        """添加变量监视"""
        watch = Watch(name=name, expression=expression)
        self.watches.append(watch)
        return watch
    
    def remove_watch(self, name: str) -> bool:
        """移除变量监视"""
        for i, w in enumerate(self.watches):
            if w.name == name:
                del self.watches[i]
                return True
        return False
    
    def update_watches(self):
        """更新所有监视变量的值"""
        now = datetime.now()
        for watch in self.watches:
            try:
                value = eval(watch.expression, {}, self.current_variables)
                watch.value = value
                watch.type_name = type(value).__name__
                watch.last_updated = now
            except Exception as e:
                watch.value = f"<error: {e}>"
                watch.type_name = "error"
    
    def get_watch_values(self) -> List[Dict]:
        """获取所有监视变量的值"""
        self.update_watches()
        return [
            {
                "name": w.name,
                "expression": w.expression,
                "value": str(w.value),
                "type": w.type_name
            }
            for w in self.watches
        ]
    
    # ==================== 执行控制 ====================
    
    def run_script(self, file_path: str, inputs: Dict = None) -> Dict:
        """
        运行脚本 (带调试支持)
        
        Args:
            file_path: 脚本路径
            inputs: 输入变量
            
        Returns:
            Dict: 执行结果
        """
        from ..nexa_parser import parse
        from ..ast_transformer import NexaTransformer
        from ..code_generator import CodeGenerator
        
        self.state = DebuggerState.RUNNING
        self._log_event("execution_start", message=f"开始执行: {file_path}")
        
        inputs = inputs or {}
        
        try:
            # 读取源码
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            
            # 编译
            tree = parse(source)
            transformer = NexaTransformer()
            ast = transformer.transform(tree)
            
            # 注入调试钩子
            py_code = self._inject_debug_hooks(CodeGenerator(ast).generate())
            
            # 创建临时模块执行
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(py_code)
                temp_path = f.name
            
            try:
                module_name = "nexa_debug_" + os.path.basename(temp_path).replace('.py', '')
                spec = importlib.util.spec_from_file_location(module_name, temp_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                
                # 捕获输出
                f_out = io.StringIO()
                with contextlib.redirect_stdout(f_out):
                    spec.loader.exec_module(module)
                    
                    for k, v in inputs.items():
                        setattr(module, k, v)
                    
                    result = None
                    if hasattr(module, 'flow_main'):
                        result = module.flow_main()
            finally:
                os.unlink(temp_path)
            
            self.state = DebuggerState.STOPPED
            self._log_event("execution_end", message="执行完成")
            
            return {
                "success": True,
                "result": result,
                "stdout": f_out.getvalue()
            }
            
        except Exception as e:
            self.state = DebuggerState.STOPPED
            self._log_event(
                "execution_error",
                message=str(e),
                stack_trace=traceback.format_exc()
            )
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    def _inject_debug_hooks(self, code: str) -> str:
        """注入调试钩子到生成的代码"""
        # 在代码开头注入调试器引用
        debug_init = """
# === Debug Hooks ===
__nexa_debugger__ = None

def __nexa_debug_hook__(hook_type, name, **kwargs):
    global __nexa_debugger__
    if __nexa_debugger__:
        __nexa_debugger__._handle_hook(hook_type, name, kwargs)

def __nexa_break__(bp_type, target, context=None):
    global __nexa_debugger__
    if __nexa_debugger__:
        __nexa_debugger__._check_breakpoint(bp_type, target, context or {})
# ===================

"""
        return debug_init + code
    
    def _handle_hook(self, hook_type: str, name: str, kwargs: Dict):
        """处理调试钩子"""
        self._log_event(
            hook_type,
            message=f"{hook_type}: {name}",
            variables=kwargs
        )
        
        # 更新当前变量
        self.current_variables.update(kwargs)
        self.update_watches()
        
        # 检查断点
        self._check_breakpoint(hook_type, name, kwargs)
    
    def _check_breakpoint(self, bp_type: str, target: str, context: Dict):
        """检查是否命中断点"""
        for bp in self.breakpoints:
            if bp.bp_type.value == bp_type and bp.target == target:
                if bp.should_break(context):
                    bp.hit_count += 1
                    self._on_hit_breakpoint(bp, context)
    
    def _on_hit_breakpoint(self, bp: Breakpoint, context: Dict):
        """命中断点时的处理"""
        self.state = DebuggerState.PAUSED
        self._log_event(
            "breakpoint_hit",
            message=f"命中断点: {bp.bp_type.value} '{bp.target}'",
            variables=context
        )
        
        # 调用回调
        if self._on_breakpoint:
            self._on_breakpoint(bp, context)
        
        # 等待继续执行
        while self.state == DebuggerState.PAUSED:
            import time
            time.sleep(0.1)
    
    def continue_execution(self):
        """继续执行"""
        if self.state == DebuggerState.PAUSED:
            self.state = DebuggerState.RUNNING
    
    def step_over(self):
        """单步跳过"""
        if self.state == DebuggerState.PAUSED:
            self.state = DebuggerState.STEPPING
    
    def step_into(self):
        """单步进入"""
        if self.state == DebuggerState.PAUSED:
            self.state = DebuggerState.STEPPING
    
    def step_out(self):
        """单步跳出"""
        if self.state == DebuggerState.PAUSED:
            self.state = DebuggerState.RUNNING
    
    def stop(self):
        """停止执行"""
        self.state = DebuggerState.STOPPED
    
    # ==================== 事件日志 ====================
    
    def _log_event(self, event_type: str, **kwargs):
        """记录调试事件"""
        event = DebugEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            **kwargs
        )
        self.events.append(event)
        
        # 限制事件数量
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
    
    def get_events(self, event_type: str = None) -> List[Dict]:
        """获取事件列表"""
        events = self.events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return [
            {
                "type": e.event_type,
                "timestamp": e.timestamp.isoformat(),
                "message": e.message,
                "variables": e.variables,
                "stack_trace": e.stack_trace
            }
            for e in events
        ]
    
    def clear_events(self):
        """清空事件日志"""
        self.events.clear()
    
    # ==================== 回调设置 ====================
    
    def on_breakpoint(self, callback: Callable):
        """设置断点回调"""
        self._on_breakpoint = callback
    
    def on_step(self, callback: Callable):
        """设置单步回调"""
        self._on_step = callback
    
    def on_error(self, callback: Callable):
        """设置错误回调"""
        self._on_error = callback
    
    # ==================== 状态查询 ====================
    
    def get_state(self) -> Dict:
        """获取调试器状态"""
        return {
            "state": self.state.value,
            "breakpoints_count": len(self.breakpoints),
            "watches_count": len(self.watches),
            "events_count": len(self.events),
            "call_stack": self.call_stack.copy(),
            "variables": self.current_variables.copy()
        }
    
    def get_call_stack(self) -> List[str]:
        """获取调用栈"""
        return self.call_stack.copy()
    
    def get_variables(self) -> Dict[str, Any]:
        """获取当前变量"""
        return self.current_variables.copy()


# ==================== 全局调试器 ====================

_global_debugger: Optional[NexaDebugger] = None


def get_debugger() -> NexaDebugger:
    """获取全局调试器实例"""
    global _global_debugger
    if _global_debugger is None:
        _global_debugger = NexaDebugger()
    return _global_debugger


def init_debugger() -> NexaDebugger:
    """初始化新的调试器"""
    global _global_debugger
    _global_debugger = NexaDebugger()
    return _global_debugger


# ==================== 导入 tempfile ====================
import tempfile