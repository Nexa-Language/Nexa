"""
Nexa Result Types — Error Propagation Infrastructure

v1.2: 实现 ? 操作符和 otherwise 内联错误处理的核心类型

设计参考: NTNT 的 ? 操作符和 otherwise 语句
- NexaResult: 类似 Rust Result<T, E>，成功(ok)或失败(err)
- NexaOption: 类似 Rust Option<T>，有值(some)或无值(none)
- ErrorPropagation: ? 操作符触发的内部异常，用于 early-return
- propagate_or_else: 统一处理 ? 和 otherwise 逻辑
- try_propagate: 在 flow 函数中捕获 ErrorPropagation 并转换为错误返回

关键设计原则:
1. Agent 优先: ? 和 otherwise 首先为 Agent.run() 结果设计
2. 向后兼容: 字符串结果自动包装为 NexaResult.ok
3. ErrorPropagation 是内部机制，不是用户可见的异常类型
4. 与 DAG ?? 条件分支操作符不冲突
"""


class ErrorPropagation(Exception):
    """? 操作符触发的错误传播异常，用于 early-return
    
    这是 Nexa 内部机制，不是用户可见的异常类型。
    当 ? 操作符遇到 NexaResult.err 或 NexaOption.none 时，
    抛出此异常，flow 函数的外层 try_propagate 会捕获并转换为错误返回。
    
    类似 Rust 的 ? 操作符工作机制：
    - Ok/Some → 继续执行（unwrap 返回值）
    - Err/None → 抛出 ErrorPropagation → flow 函数捕获 → 返回错误
    """
    def __init__(self, error):
        self.error = error
        super().__init__(str(error))


class NexaResult:
    """Nexa 结果包装器，类似 Rust 的 Result<T, E>
    
    表示一个可能成功或失败的操作结果：
    - NexaResult.ok(value) — 操作成功，包含返回值
    - NexaResult.err(error) — 操作失败，包含错误信息
    
    使用示例:
        result = NexaResult.ok("success data")
        result.is_ok  # True
        result.value   # "success data"
        
        result = NexaResult.err("something went wrong")
        result.is_err  # True
        result.error   # "something went wrong"
    
    ? 操作符核心:
        result.unwrap()  # 成功→返回值，失败→抛 ErrorPropagation
        
    otherwise 核心:
        result.unwrap_or("default")  # 成功→返回值，失败→返回默认值
    """
    
    def __init__(self, value=None, error=None, is_ok=True):
        self._value = value
        self._error = error
        self._is_ok = is_ok
    
    @staticmethod
    def ok(value):
        """创建成功结果"""
        return NexaResult(value=value, is_ok=True)
    
    @staticmethod
    def err(error):
        """创建失败结果"""
        return NexaResult(error=error, is_ok=False)
    
    @property
    def is_ok(self):
        """是否成功"""
        return self._is_ok
    
    @property
    def is_err(self):
        """是否失败"""
        return not self._is_ok
    
    @property
    def value(self):
        """成功时的值（仅在 is_ok 时有效）"""
        return self._value
    
    @property
    def error(self):
        """失败时的错误（仅在 is_err 时有效）"""
        return self._error
    
    def unwrap(self):
        """? 操作符的核心：成功返回值，失败则触发 ErrorPropagation
        
        这是 ? 操作符的工作原理：
        - NexaResult.ok → 返回内部值，继续执行
        - NexaResult.err → 抛出 ErrorPropagation，触发 early-return
        
        Returns:
            成功时的内部值
        
        Raises:
            ErrorPropagation: 失败时抛出，包含错误信息
        """
        if self._is_ok:
            return self._value
        raise ErrorPropagation(self._error)
    
    def unwrap_or(self, default):
        """otherwise 的核心：成功返回值，失败返回默认值
        
        这是 otherwise 的工作原理：
        - NexaResult.ok → 返回内部值
        - NexaResult.err → 返回 default
        
        Args:
            default: 失败时的默认值
        
        Returns:
            成功时的内部值，或失败时的默认值
        """
        if self._is_ok:
            return self._value
        return default
    
    def unwrap_or_else(self, handler):
        """otherwise 的函数版本：成功返回值，失败执行 handler
        
        Args:
            handler: 失败时的处理函数，接收 error 参数
        
        Returns:
            成功时的内部值，或 handler 的返回值
        """
        if self._is_ok:
            return self._value
        return handler(self._error)
    
    def map(self, fn):
        """映射成功值：成功时应用 fn，失败时保持不变
        
        Args:
            fn: 成功值的映射函数
        
        Returns:
            新的 NexaResult
        """
        if self._is_ok:
            return NexaResult.ok(fn(self._value))
        return self
    
    def map_err(self, fn):
        """映射错误值：失败时应用 fn，成功时保持不变
        
        Args:
            fn: 错误值的映射函数
        
        Returns:
            新的 NexaResult
        """
        if not self._is_ok:
            return NexaResult.err(fn(self._error))
        return self
    
    def and_then(self, fn):
        """链式操作：成功时应用 fn（fn 返回新的 NexaResult），失败时保持不变
        
        Args:
            fn: 成功值的链式函数，返回 NexaResult
        
        Returns:
            fn 返回的 NexaResult，或原始的 err
        """
        if self._is_ok:
            return fn(self._value)
        return self
    
    def or_else(self, fn):
        """链式错误恢复：失败时应用 fn（fn 返回新的 NexaResult），成功时保持不变
        
        Args:
            fn: 错误值的恢复函数，返回 NexaResult
        
        Returns:
            fn 返回的 NexaResult，或原始的 ok
        """
        if not self._is_ok:
            return fn(self._error)
        return self
    
    def __repr__(self):
        if self._is_ok:
            return f"NexaResult.ok({self._value!r})"
        return f"NexaResult.err({self._error!r})"
    
    def __str__(self):
        if self._is_ok:
            return str(self._value)
        return f"Error: {self._error}"
    
    def __eq__(self, other):
        if not isinstance(other, NexaResult):
            return False
        return self._is_ok == other._is_ok and (
            self._value == other._value if self._is_ok else self._error == other._error
        )


class NexaOption:
    """Nexa 可选值包装器，类似 Rust 的 Option<T>
    
    表示一个可能有值或无值的结果：
    - NexaOption.some(value) — 有值
    - NexaOption.none() — 无值
    
    使用示例:
        opt = NexaOption.some("hello")
        opt.is_some  # True
        opt.value    # "hello"
        
        opt = NexaOption.none()
        opt.is_none  # True
    """
    
    def __init__(self, value=None, is_some=True):
        self._value = value
        self._is_some = is_some
    
    @staticmethod
    def some(value):
        """创建有值的 Option"""
        return NexaOption(value=value, is_some=True)
    
    @staticmethod
    def none():
        """创建无值的 Option"""
        return NexaOption(is_some=False)
    
    @property
    def is_some(self):
        """是否有值"""
        return self._is_some
    
    @property
    def is_none(self):
        """是否无值"""
        return not self._is_some
    
    @property
    def value(self):
        """内部值（仅在 is_some 时有效）"""
        return self._value
    
    def unwrap(self):
        """? 操作符的核心：有值返回值，无值则触发 ErrorPropagation
        
        Returns:
            内部值
        
        Raises:
            ErrorPropagation: 无值时抛出
        """
        if self._is_some:
            return self._value
        raise ErrorPropagation(None)
    
    def unwrap_or(self, default):
        """otherwise 的核心：有值返回值，无值返回默认值
        
        Args:
            default: 无值时的默认值
        
        Returns:
            内部值或默认值
        """
        if self._is_some:
            return self._value
        return default
    
    def unwrap_or_else(self, handler):
        """otherwise 的函数版本：有值返回值，无值执行 handler
        
        Args:
            handler: 无值时的处理函数
        
        Returns:
            内部值或 handler 的返回值
        """
        if self._is_some:
            return self._value
        return handler()
    
    def map(self, fn):
        """映射有值情况：有值时应用 fn，无值时保持不变
        
        Args:
            fn: 值的映射函数
        
        Returns:
            新的 NexaOption
        """
        if self._is_some:
            return NexaOption.some(fn(self._value))
        return self
    
    def and_then(self, fn):
        """链式操作：有值时应用 fn（fn 返回 NexaOption），无值时保持不变
        
        Args:
            fn: 值的链式函数，返回 NexaOption
        
        Returns:
            fn 返回的 NexaOption，或原始的 none
        """
        if self._is_some:
            return fn(self._value)
        return self
    
    def or_else(self, fn):
        """链式无值恢复：无值时应用 fn，有值时保持不变
        
        Args:
            fn: 无值时的恢复函数，返回 NexaOption
        
        Returns:
            fn 返回的 NexaOption，或原始的 some
        """
        if not self._is_some:
            return fn()
        return self
    
    def to_result(self, error=None):
        """转换为 NexaResult：有值→ok，无值→err
        
        Args:
            error: 无值时的错误信息
        
        Returns:
            NexaResult
        """
        if self._is_some:
            return NexaResult.ok(self._value)
        return NexaResult.err(error)
    
    def __repr__(self):
        if self._is_some:
            return f"NexaOption.some({self._value!r})"
        return "NexaOption.none()"
    
    def __str__(self):
        if self._is_some:
            return str(self._value)
        return "None"
    
    def __eq__(self, other):
        if not isinstance(other, NexaOption):
            return False
        return self._is_some == other._is_some and (
            self._value == other._value if self._is_some else True
        )


# ============================================================
# 运行时辅助函数
# ============================================================

def propagate_or_else(result, otherwise_handler=None):
    """统一处理 ? 和 otherwise 逻辑
    
    这是 Nexa ? 操作符和 otherwise 语句的运行时核心函数。
    
    当只有 result 参数时（? 操作符模式）：
        - 成功 → 返回值
        - 失败 → 抛出 ErrorPropagation（early-return）
    
    当有 otherwise_handler 参数时（otherwise 模式）：
        - 成功 → 返回值
        - 失败 → 执行 otherwise_handler
    
    otherwise_handler 可以是:
        - 值（字符串、数字等）→ unwrap_or
        - NexaAgent 实例 → Agent.run() 作为 fallback
        - 函数/lambda → unwrap_or_else
        - dict（代码块）→ 执行代码块中的语句
    
    Args:
        result: NexaResult 或 NexaOption 实例
        otherwise_handler: otherwise 语句的处理器（可选）
    
    Returns:
        成功时的值，或 otherwise_handler 处理后的值
    
    Raises:
        ErrorPropagation: ? 操作符模式下失败时抛出
    """
    # 先检查是否已经是 NexaResult/NexaOption
    if isinstance(result, NexaResult):
        if result.is_ok:
            return result.value
        if otherwise_handler is not None:
            return _handle_otherwise(result.error, otherwise_handler)
        raise ErrorPropagation(result.error)
    
    if isinstance(result, NexaOption):
        if result.is_some:
            return result.value
        if otherwise_handler is not None:
            return _handle_otherwise(None, otherwise_handler)
        raise ErrorPropagation(None)
    
    # 向后兼容：非 NexaResult/NexaOption 值视为成功
    # Agent.run() 返回字符串时自动包装为 NexaResult.ok
    return result


def _handle_otherwise(error, handler):
    """处理 otherwise handler
    
    Args:
        error: 错误信息（来自 NexaResult.err 或 NexaOption.none）
        handler: otherwise 处理器
    
    Returns:
        handler 处理后的值
    """
    # handler 是 NexaAgent 实例 → 执行 Agent.run() 作为 fallback
    # 这是 Nexa 独有的特性：otherwise 可以指定另一个 Agent 作为 fallback
    from .agent import NexaAgent
    if isinstance(handler, NexaAgent):
        # Agent fallback: 调用 handler.run(str(error))
        # Agent.run() 本身会返回 NexaResult，所以需要 propagate_or_else
        agent_result = handler.run_result(str(error))
        if agent_result.is_ok:
            return agent_result.value
        # Agent fallback 也失败了 → 返回 Agent 的错误信息作为最终结果
        return str(agent_result.error)
    
    # handler 是函数/lambda → unwrap_or_else
    if callable(handler):
        return handler(error)
    
    # handler 是字典（代码块描述）→ 执行代码块中的语句
    if isinstance(handler, dict):
        # 代码块处理器 — 包含需要执行的语句列表
        # 这由 code_generator 生成的 Python 代码处理
        # 在运行时直接返回字典中的 "result" 字段
        if "result" in handler:
            return handler["result"]
        if "statements" in handler:
            # 执行语句列表（由生成的 Python 代码负责）
            return handler.get("fallback_value", str(error))
        return handler
    
    # handler 是值（字符串、数字等）→ 直接返回作为默认值
    return handler


def try_propagate(flow_func, *args, **kwargs):
    """在 flow 函数中捕获 ErrorPropagation 并转换为错误返回
    
    这是 flow 函数的外层包裹逻辑：
    - 正常执行 → 返回函数结果
    - ? 操作符触发 ErrorPropagation → 捕获并返回 NexaResult.err
    
    每个 flow 函数生成的 Python 代码都应该被 try_propagate 包裹，
    使得 ? 操作符的 early-return 行为正确工作。
    
    Args:
        flow_func: flow 函数
        *args: 函数参数
        **kwargs: 函数关键字参数
    
    Returns:
        函数正常返回值（可能是 NexaResult.ok 或原始值）
        或 NexaResult.err（当 ? 操作符触发 early-return）
    """
    try:
        result = flow_func(*args, **kwargs)
        # 如果结果已经是 NexaResult，直接返回
        if isinstance(result, NexaResult):
            return result
        # 否则包装为 NexaResult.ok
        return NexaResult.ok(result)
    except ErrorPropagation as e:
        # ? 操作符触发的 early-return → 转换为 NexaResult.err
        return NexaResult.err(e.error)
    except Exception as e:
        # 其他异常 → 也转换为 NexaResult.err（但不改变原有异常类型行为）
        # 注意：这里不捕获 ContractViolation 等用户可见的异常
        # 只有 ErrorPropagation 是内部机制
        from .contracts import ContractViolation
        from .type_system import TypeViolation
        if isinstance(e, (ContractViolation, TypeViolation)):
            raise  # 用户可见的异常，不转换
        return NexaResult.err(str(e))


def wrap_agent_result(raw_result):
    """将 Agent.run() 的原始返回值包装为 NexaResult
    
    向后兼容策略：
    - 如果已经是 NexaResult → 直接返回
    - 如果是字符串 → NexaResult.ok(string)
    - 如果是 Pydantic 模型 → NexaResult.ok(model)
    - 如果抛出异常 → NexaResult.err(exception_message)
    
    Args:
        raw_result: Agent.run() 的原始返回值
    
    Returns:
        NexaResult 包装
    """
    if isinstance(raw_result, NexaResult):
        return raw_result
    # 成功的字符串/Pydantic 模型结果 → NexaResult.ok
    return NexaResult.ok(raw_result)