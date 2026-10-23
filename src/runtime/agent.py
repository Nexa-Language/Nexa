# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
# 
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# Nexa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
# ========================================================================

from typing import Any, Callable, Dict, List, Optional
from .secrets import DEFAULT_MODEL_CONFIG, DEFAULT_OPENAI_COMPATIBLE_BASE_URL, nexa_secrets
from .contracts import ContractSpec, ContractClause, ContractViolation, check_requires, check_ensures, capture_old_values, OldValues
from .type_system import TypeChecker, TypeViolation, TypeMode, get_type_mode, TypeInferrer, PrimitiveTypeExpr, AliasTypeExpr
from .result_types import NexaResult, NexaOption, ErrorPropagation, wrap_agent_result
from openai import OpenAI
import json
import os
import sys
import hashlib
import threading
from .run_state import RunConfig, RunState, RunStatus, RunStopped
from .providers import ChatCompletionsProvider, ModelProvider

class NexaQuotaExceededError(Exception):
    pass

class NexaTimeoutError(Exception):
    """Raised when agent execution times out"""
    pass

from .memory import global_memory
from .tools_registry import execute_tool
from .cache_manager import get_cache_manager, NexaCacheManager
from .cow_state import CowAgentState
from .agent_context import AgentContext, ContextSpec
# v2.2.1: UI-aware output — suppress debug prints when NEXA_QUIET is set
import os as _os
def _debug_print(*args, **kwargs):
    """Print only when NEXA_QUIET is not set. Used for runtime debug output
    that should be suppressed when a UI layer (e.g. nexa_code REPL) controls output."""
    if not _os.environ.get("NEXA_QUIET"):
        print(*args, **kwargs)


class NexaAgent:
    def __init__(self, name: str, prompt: str = "", tools: List[Dict[str, Any]] = None,
                 model: str = None, role: str = "", memory_scope: str = "local",
                 protocol=None, max_tokens=None, stream=False, cache=False,
                 max_history_turns=None, experience=None, timeout: int = 30, retry: int = 3,
                 contracts=None, output_format: str = "", output_schema=None,
                 max_tool_calls: int = 10, tool_call_strategy: str = "auto",
                 context_spec=None, provider_api: Optional[str] = None):
        # v2.2.1: Context-as-Structure — context behaviour declared at construction
        self.context_spec = ContextSpec.from_dict(context_spec) if isinstance(context_spec, dict) else context_spec
        self._last_context: Optional[AgentContext] = None
        self._artifacts: Dict[str, Any] = {}
        self._tool_results: List[Dict[str, Any]] = []
        self._last_output_text: str = ""

        self.name = name
        self._run_lock = threading.RLock()
        self.last_run: Optional[RunState] = None
        self.system_prompt = prompt
        if role:
            self.system_prompt = f"Role: {role}. {self.system_prompt}".strip()
        
        # 如果有 protocol，添加 JSON 格式要求到 system prompt
        self.protocol = protocol
        if self.protocol:
            # 获取 protocol 的字段定义
            if hasattr(self.protocol, 'model_json_schema'):
                schema = self.protocol.model_json_schema()
                fields = list(schema.get('properties', {}).keys())
            else:
                fields = [f for f in dir(self.protocol) if not f.startswith('_')]
            
            json_instruction = f"\n\nIMPORTANT: You MUST respond with a valid JSON object containing these fields: {', '.join(fields)}. Do not include any text outside the JSON object."
            self.system_prompt += json_instruction
            
        if experience and os.path.exists(experience):
            with open(experience, "r", encoding="utf-8") as f:
                exp_content = f.read()
            self.system_prompt += f"\n\n[Experience / Long-term Memory]:\n{exp_content}"
            
        self.tools = tools or []
        
        self.provider = "default"
        self.model = model or nexa_secrets.get_model_config().get("strong", DEFAULT_MODEL_CONFIG["strong"])
        if "/" in self.model:
            self.provider, self.model = self.model.split("/", 1)
        self.provider_api = provider_api or ("anthropic" if self.provider == "anthropic" else "chat")
        if self.provider_api not in {"chat", "responses", "anthropic"}:
            raise ValueError(f"Unsupported provider API: {self.provider_api}")
        self._native_client: Any = None
        self._provider_items: List[Dict[str, Any]] = []
        self._provider_cursor = 0
            
        self.memory_scope = memory_scope
        # protocol 已在上面处理
        self.max_tokens = max_tokens
        self.stream = stream
        self.cache = cache
        self.max_history_turns = max_history_turns
        self.messages = []
        
        # 新增: timeout 和 retry 属性
        self.timeout = timeout  # 请求超时时间（秒）
        self.retry = retry      # 最大重试次数

        # v2.1: output_format / output_schema / max_tool_calls / tool_call_strategy
        self.output_format = output_format  # "" | "json"
        self.output_schema = output_schema  # Pydantic model or None
        self.max_tool_calls = max_tool_calls  # max tool call rounds per request
        self.tool_call_strategy = tool_call_strategy  # "auto" | "required" | "none"
        self._tool_call_count = 0  # counter for current request
        
        # Design by Contract: 契约规格
        self.contracts = contracts  # ContractSpec 或 None
        
        # COW 状态管理 - 用于 O(1) 克隆和 Tree-of-Thoughts 模式
        self._cow_state = CowAgentState()
        # 将配置存入 COW 状态，使 clone() 能共享这些配置
        self._cow_state.set("system_prompt", self.system_prompt)
        self._cow_state.set("provider", self.provider)
        self._cow_state.set("model", self.model)
        self._cow_state.set("tools", self.tools)
        self._cow_state.set("max_tokens", self.max_tokens)
        self._cow_state.set("stream", self.stream)
        self._cow_state.set("cache", self.cache)
        self._cow_state.set("max_history_turns", self.max_history_turns)
        self._cow_state.set("timeout", self.timeout)
        self._cow_state.set("retry", self.retry)
        
        # Load from persistent memory
        self.memory_file = None
        if self.memory_scope == "persistent":
            os.makedirs(".nexa_cache", exist_ok=True)
            self.memory_file = f".nexa_cache/{self.name}_memory.json"
            if os.path.exists(self.memory_file):
                try:
                    with open(self.memory_file, "r", encoding="utf-8") as f:
                        self.messages = json.load(f)
                except Exception:
                    pass
                    
        if not self.messages and self.system_prompt:
            self.messages.append({"role": "system", "content": self.system_prompt})
            
        # LLM client is initialized lazily so local compilation, inspection, and
        # unit tests can construct agents without requiring external credentials.
        self.client = None
        self._client_base_url = None

        if os.environ.get("NEXA_DEBUG"):
            configured_key, configured_base_url = self._resolve_provider_config()
            print(f"[Agent:{name}] Active config: {nexa_secrets.get_active_config_name()}")
            print(f"[Agent:{name}] Provider: {self.provider}")
            print(f"[Agent:{name}] Model: {self.model}")
            print(f"[Agent:{name}] Base URL: {configured_base_url}")
            print(f"[Agent:{name}] API key configured: {bool(configured_key)}")

    def _resolve_provider_config(self) -> tuple[str, str]:
        """Resolve provider credentials without logging or validating secrets."""
        api_key, base_url = nexa_secrets.get_provider_config(self.provider)

        if not api_key:
            api_key = nexa_secrets.get("API_KEY") or nexa_secrets.get(f"{self.provider.upper()}_API_KEY")
        if not base_url:
            base_url = nexa_secrets.get("BASE_URL") or nexa_secrets.get(f"{self.provider.upper()}_BASE_URL")

        if base_url:
            return api_key, base_url
        return api_key, DEFAULT_OPENAI_COMPATIBLE_BASE_URL

    def _default_summary_model(self) -> str:
        """Use the configured weak model for low-cost context summaries."""
        return nexa_secrets.get_model_config().get("weak", DEFAULT_MODEL_CONFIG["weak"])

    def _provider_adapter(self) -> ModelProvider:
        from .native_providers import AnthropicProvider, ResponsesProvider

        if self.provider_api == "responses":
            return ResponsesProvider(self._get_client)
        if self.provider_api == "anthropic":
            return AnthropicProvider(self._get_anthropic_client)
        return ChatCompletionsProvider(self._get_client)

    def _get_anthropic_client(self) -> Any:
        with self._run_lock:
            if self._native_client is not None:
                return self._native_client
            from anthropic import Anthropic

            api_key = nexa_secrets.get("ANTHROPIC_API_KEY")
            base_url = nexa_secrets.get("ANTHROPIC_BASE_URL")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY is required for the native Anthropic API")
            options = {"api_key": api_key, "max_retries": 0}
            if base_url:
                options["base_url"] = base_url
            self._native_client = Anthropic(**options)
            return self._native_client

    def _get_client(self) -> OpenAI:
        """Create the OpenAI-compatible client only when a model call is required."""
        with self._run_lock:
            if self.client is not None:
                return self.client

            api_key, base_url = self._resolve_provider_config()
            if not api_key:
                raise ValueError(
                    f"API key not found for provider '{self.provider}'. "
                    f"Configure secrets.nxs with API_KEY or {self.provider.upper()}_API_KEY before running this agent."
                )

            self._client_base_url = base_url
            self.client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0)
            return self.client

    # v1.1: 渐进式类型系统 — 初始化 Agent 级别类型检查器
    _type_checker_instance = None
    
    @classmethod
    def _get_type_checker(cls) -> TypeChecker:
        """获取全局类型检查器实例（懒加载）"""
        if cls._type_checker_instance is None:
            cls._type_checker_instance = TypeChecker()
        return cls._type_checker_instance
    
    def _check_output_type(self, result: Any) -> Any:
        """v1.1: 渐进式类型系统 — 检查 Agent 输出与 Protocol 的类型合规性
        
        根据 NEXA_TYPE_MODE:
        - STRICT:    类型不匹配=抛 TypeViolation 异常
        - WARN:      类型不匹配=日志警告并继续
        - FORGIVING: 静默忽略
        
        Args:
            result: Agent 执行结果（可能是 Pydantic 模型实例或字符串）
        
        Returns:
            原始 result（如果所有类型检查通过或处于 forgiving/warn 模式）
        
        Raises:
            TypeViolation: 如果 strict 模式下类型不匹配
        """
        type_mode = get_type_mode()
        if type_mode == TypeMode.FORGIVING:
            return result  # forgiving 模式完全跳过类型检查
        
        # 如果有 protocol，检查输出数据与 protocol 字段类型的合规性
        if self.protocol and hasattr(self.protocol, '__name__'):
            checker = self._get_type_checker()
            protocol_name = self.protocol.__name__
            
            # 尝试将结果转换为字典进行检查
            if hasattr(result, 'model_dump'):
                # Pydantic v2 模型
                result_dict = result.model_dump()
            elif hasattr(result, 'dict'):
                # Pydantic v1 模型
                result_dict = result.dict()
            elif isinstance(result, dict):
                result_dict = result
            elif isinstance(result, str):
                # 纯字符串结果 — 尝试解析为 JSON
                try:
                    import json
                    result_dict = json.loads(result)
                except (json.JSONDecodeError, ValueError):
                    # 字符串不是 JSON — 无法检查 protocol 合规性
                    if type_mode == TypeMode.STRICT:
                        raise TypeViolation(
                            f"Agent '{self.name}' output is a string, not a JSON object matching protocol '{protocol_name}'",
                            expected_type=AliasTypeExpr(protocol_name),
                            actual_type=PrimitiveTypeExpr("str"),
                            value=result,
                            context={"agent": self.name, "protocol": protocol_name}
                        )
                    elif type_mode == TypeMode.WARN:
                        import logging
                        logging.getLogger("nexa.type_system").warning(
                            f"⚠️ Agent '{self.name}' output is a string, not matching protocol '{protocol_name}'"
                        )
                    return result
            else:
                return result  # 未知结果类型，跳过
            
            # 检查 Protocol 合规性
            type_result = checker.check_protocol_compliance(result_dict, protocol_name)
            checker.handle_violation(type_result)
        
        return result
    
    def _check_ensures_contract(self, result: Any, old_values: Optional[OldValues] = None, *, input_text: Optional[str] = None) -> Any:
        """Design by Contract: 检查后置条件 (ensures) + v1.1 类型检查
        
        如果有契约且 ensures 检查失败:
        - Agent ensures 失败: 触发重试（如果有 @retry）或抛 ContractViolation
        
        v1.1: 在 ensures 检查之后，还会进行输出类型合规性检查。
        
        Args:
            result: Agent 执行结果
            old_values: 入口时捕获的值
        
        Returns:
            原始 result（如果所有条件满足）
        
        Raises:
            ContractViolation: 如果 ensures 条件不满足
            TypeViolation: 如果 strict 模式下类型不匹配
        """
        if not self.contracts or not self.contracts.has_ensures():
            # v1.1: 即使没有 ensures 契约，也执行类型检查
            return self._check_output_type(result)
        
        if input_text is None:
            input_text = next((str(message.get("content", "")) for message in reversed(self.messages) if message.get("role") == "user"), "")
        context = {"result": result, "input": input_text}
        ens_violation = check_ensures(self.contracts, context, result, old_values)
        if ens_violation:
            print(f"[{self.name} Contract] Ensures violated: {ens_violation.args[0]}")
            raise ContractViolation(
                ens_violation.args[0],
                clause_type=ens_violation.clause_type,
                clause=ens_violation.clause,
                context=ens_violation.context,
                is_semantic=ens_violation.is_semantic
            )
        # v1.1: ensures 通过后，执行类型检查
        return self._check_output_type(result)

    def _save_memory(self):
        if self.memory_file:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.messages, f, ensure_ascii=False, indent=2)

    def _get_cache_key(self, kwargs):
        data = json.dumps({
            "messages": self.messages,
            "tools": kwargs.get("tools", []),
            "model": self.model
        }, sort_keys=True)
        return hashlib.md5(data.encode("utf-8")).hexdigest()
        
    def _check_cache(self, kwargs):
        """使用增强的缓存管理器检查缓存"""
        if not self.cache:
            return None
        # 使用新的缓存管理器
        cache_mgr = get_cache_manager()
        return cache_mgr.get(
            messages=self.messages,
            model=self.model,
            tools=kwargs.get("tools", []),
            use_semantic=True
        )
            
    def _write_cache(self, kwargs, result):
        """使用增强的缓存管理器写入缓存"""
        if not self.cache:
            return
        # 使用新的缓存管理器
        cache_mgr = get_cache_manager()
        cache_mgr.set(
            messages=self.messages,
            model=self.model,
            result=result,
            tools=kwargs.get("tools", [])
        )

    def _compact_context(self):
        if not self.max_history_turns:
            return
        # Count user messages
        user_msgs = [m for m in self.messages if m.get("role") == "user"]
        if len(user_msgs) > self.max_history_turns:
            sys_msgs = [m for m in self.messages if m.get("role") == "system"]
            keep_user_count = 0
            keep_idx = len(self.messages)
            for i in range(len(self.messages)-1, -1, -1):
                if self.messages[i].get("role") == "user":
                    keep_user_count += 1
                    if keep_user_count > self.max_history_turns:
                        keep_idx = i + 1
                        break
            
            if keep_idx > len(sys_msgs):
                to_summarize = self.messages[len(sys_msgs):keep_idx]
                if to_summarize:
                    sum_prompt = "Please summarize the following conversation history concisely:\n" + json.dumps(to_summarize, ensure_ascii=False)
                    summary_model = self._default_summary_model() if getattr(self, "provider", "default") == "default" else self.model
                    
                    try:
                        client = self._get_client()
                        summary_res = client.chat.completions.create(
                            model=summary_model,
                            messages=[{"role": "user", "content": sum_prompt}]
                        )
                        summary = summary_res.choices[0].message.content
                        self.messages = sys_msgs + [{"role": "system", "content": f"Previous conversation summary: {summary}"}] + self.messages[keep_idx:]
                    except Exception as e:
                        _debug_print(f"[{self.name} Context Compaction Failed]: {e}")

    def run(self, *args) -> Any:
        """Run one turn in the legacy serialized conversation; execute() starts an isolated run."""
        from .agent_execution import execute_agent

        with self._run_lock:
            outcome = execute_agent(self, args, history=self.messages, on_text=lambda text: print(text, end="", flush=True))
            self.last_run = outcome.state
            if not outcome.state.success:
                if outcome.state.status == RunStatus.TIMED_OUT:
                    raise NexaTimeoutError(outcome.state.error)
                if outcome.state.status == RunStatus.BUDGET_EXHAUSTED:
                    raise NexaQuotaExceededError(outcome.state.error)
                if outcome.exception is not None:
                    raise outcome.exception
                raise RunStopped(outcome.state.status, outcome.state.error or outcome.state.status.value)
            self.messages = outcome.state.messages
            self._provider_items = outcome.state.provider_items
            self._provider_cursor = outcome.state.provider_cursor
            self._last_context = outcome.context
            self._last_output_text = str(outcome.value)
            self._tool_results = [{"call_id": key, **entry} for key, entry in outcome.state.tool_journal.items()]
            self._save_memory()
            return outcome.value

    def execute(self, *args: Any, config: Optional[RunConfig] = None, state: Optional[RunState] = None,
                cancel: Optional[threading.Event] = None, save=None, on_event=None, on_text=None, provider=None) -> RunState:
        """Execute or resume an isolated run. Messages and counters live in the returned RunState."""
        from .agent_execution import execute_agent

        return execute_agent(self, args, config=config, state=state, cancel=cancel, save=save,
                             on_event=on_event, on_text=on_text, provider=provider).state

    def continue_run(self, previous: RunState, *args: Any, config: Optional[RunConfig] = None,
                     cancel: Optional[threading.Event] = None, save: Optional[Callable[[RunState], None]] = None,
                     on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
                     on_text: Optional[Callable[[str], None]] = None, provider: Optional[ModelProvider] = None) -> RunState:
        """Start a new turn with settled history, fresh budgets and new approvals."""
        from .conversations import continue_agent
        return continue_agent(self, previous, args, config=config, cancel=cancel, save=save,
                              on_event=on_event, on_text=on_text, provider=provider)

    async def aexecute(self, *args: Any, **kwargs: Any) -> RunState:
        """Async adapter with cooperative cancellation at model and tool boundaries."""
        import asyncio

        cancel = kwargs.setdefault("cancel", threading.Event())
        try:
            return await asyncio.to_thread(self.execute, *args, **kwargs)
        except asyncio.CancelledError:
            cancel.set()
            raise

    def _snapshot_context(self, result: Any) -> Any:
        """v2.2.1: After run(), snapshot the agent state into an AgentContext.

        The context is stored on ``self._last_context`` so a downstream agent
        (or the pipeline runtime) can fetch it via ``last_context()``.
        The original ``result`` is returned unchanged to preserve v2.1 semantics.
        """
        self._last_output_text = str(result) if result is not None else ""
        self._last_context = AgentContext.from_agent(self)
        # Preserve v2.1 behavior: return the raw result, not the context.
        # Pipeline codegen calls last_context() explicitly when both endpoints
        # declare a context block.
        return result

    def last_context(self) -> Optional[AgentContext]:
        """Return the AgentContext produced by the most recent ``run()`` call."""
        return self._last_context

    def run_result(self, *args) -> NexaResult:
        """v1.2: 显式返回 NexaResult 包装的 Agent 执行结果
        
        与 run() 不同，此方法始终返回 NexaResult:
        - 成功 → NexaResult.ok(value)
        - 失败 → NexaResult.err(error_message)
        
        这是 ? 操作符和 otherwise 语句的核心:
        - result = Agent.run_result("query")  → NexaResult
        - result = Agent.run_result("query")? → unwrap or ErrorPropagation
        - result = Agent.run_result("query") otherwise fallback → unwrap or fallback
        
        Args:
            *args: 传递给 Agent 的输入参数
        
        Returns:
            NexaResult.ok(value) — 成功时包含返回值
            NexaResult.err(error_message) — 失败时包含错误信息
        """
        try:
            raw_result = self.run(*args)
            return wrap_agent_result(raw_result)
        except (NexaTimeoutError, NexaQuotaExceededError) as e:
            return NexaResult.err(str(e))
        except ContractViolation as e:
            return NexaResult.err(str(e))
        except Exception as e:
            return NexaResult.err(str(e))
    
    def clone(self, new_name: str, **kwargs):
        """
        创建 Agent 克隆 - 使用 Copy-on-Write (COW) 实现 O(1) 时间复杂度
        
        使用 COW 状态共享数据，只在修改时才创建本地副本。
        这对于 Tree-of-Thoughts 等需要大量分支的场景非常高效。
        
        Args:
            new_name: 新 Agent 的名称
            **kwargs: 可覆盖的属性 (model, prompt, tools, role, memory_scope,
                      protocol, max_tokens, stream, cache, max_history_turns, timeout, retry)
        
        Returns:
            新的 NexaAgent 实例，共享 COW 状态
        """
        # 使用 COW 状态克隆 - O(1) 操作
        new_cow_state = self._cow_state.clone()
        
        # 获取基础配置（从 COW 状态或 kwargs）
        model = kwargs.get("model", new_cow_state.get("provider") + "/" + new_cow_state.get("model")
                          if new_cow_state.get("provider") != "default" else new_cow_state.get("model"))
        prompt = kwargs.get("prompt", new_cow_state.get("system_prompt"))
        tools = kwargs.get("tools", new_cow_state.get("tools"))
        role = kwargs.get("role", "")
        memory_scope = kwargs.get("memory_scope", self.memory_scope)
        protocol = kwargs.get("protocol", self.protocol)
        max_tokens = kwargs.get("max_tokens", new_cow_state.get("max_tokens"))
        stream = kwargs.get("stream", new_cow_state.get("stream"))
        cache = kwargs.get("cache", new_cow_state.get("cache"))
        max_history_turns = kwargs.get("max_history_turns", new_cow_state.get("max_history_turns"))
        timeout = kwargs.get("timeout", new_cow_state.get("timeout"))
        retry = kwargs.get("retry", new_cow_state.get("retry"))
        
        # 创建新 Agent 实例
        new_agent = NexaAgent(
            name=new_name,
            prompt=prompt,
            tools=tools,
            model=model,
            role=role,
            memory_scope=memory_scope,
            protocol=protocol,
            max_tokens=max_tokens,
            stream=stream,
            cache=cache,
            max_history_turns=max_history_turns,
            timeout=timeout,
            retry=retry,
            output_schema=kwargs.get("output_schema", self.output_schema),
            output_format=kwargs.get("output_format", self.output_format),
            max_tool_calls=kwargs.get("max_tool_calls", self.max_tool_calls),
            tool_call_strategy=kwargs.get("tool_call_strategy", self.tool_call_strategy),
            contracts=kwargs.get("contracts", self.contracts),
            context_spec=kwargs.get("context_spec", self.context_spec),
            provider_api=kwargs.get("provider_api", self.provider_api),
        )
        
        # 替换为共享的 COW 状态
        new_agent._cow_state = new_cow_state
        
        return new_agent
    
    def clone_deep(self, new_name: str, **kwargs):
        """
        创建深拷贝克隆 - O(n) 时间复杂度
        
        用于性能对比测试。不使用 COW，完全复制所有数据。
        
        Args:
            new_name: 新 Agent 的名称
            **kwargs: 可覆盖的属性
        
        Returns:
            完全独立的新 NexaAgent 实例
        """
        # 使用深拷贝 COW 状态 - O(n) 操作
        new_cow_state = self._cow_state.deep_clone()
        
        # 获取配置
        model = kwargs.get("model", f"{self.provider}/{self.model}" if self.provider != "default" else self.model)
        prompt = kwargs.get("prompt", self.system_prompt)
        tools = kwargs.get("tools", list(self.tools))
        role = kwargs.get("role", "")
        memory_scope = kwargs.get("memory_scope", self.memory_scope)
        protocol = kwargs.get("protocol", self.protocol)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        stream = kwargs.get("stream", self.stream)
        cache = kwargs.get("cache", getattr(self, "cache", False))
        max_history_turns = kwargs.get("max_history_turns", getattr(self, "max_history_turns", None))
        timeout = kwargs.get("timeout", self.timeout)
        retry = kwargs.get("retry", self.retry)
        
        new_agent = NexaAgent(
            name=new_name,
            prompt=prompt,
            tools=tools,
            model=model,
            role=role,
            memory_scope=memory_scope,
            protocol=protocol,
            max_tokens=max_tokens,
            stream=stream,
            cache=cache,
            max_history_turns=max_history_turns,
            timeout=timeout,
            retry=retry,
            output_schema=kwargs.get("output_schema", self.output_schema),
            output_format=kwargs.get("output_format", self.output_format),
            max_tool_calls=kwargs.get("max_tool_calls", self.max_tool_calls),
            tool_call_strategy=kwargs.get("tool_call_strategy", self.tool_call_strategy),
            contracts=kwargs.get("contracts", self.contracts),
            context_spec=kwargs.get("context_spec", self.context_spec),
            provider_api=kwargs.get("provider_api", self.provider_api),
        )
        
        new_agent._cow_state = new_cow_state
        
        return new_agent
    
    def get_cow_stats(self):
        """获取 COW 状态的性能统计"""
        return self._cow_state.get_stats()
    
    def cow_performance_report(self) -> str:
        """获取 COW 性能报告"""
        return self._cow_state.performance_report()

    def __rshift__(self, other):
        pass
