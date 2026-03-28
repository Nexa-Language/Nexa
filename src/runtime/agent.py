from typing import Any, Dict, List
from .core import client, STRONG_MODEL
from .secrets import nexa_secrets
from openai import OpenAI
import json
import os
import sys
import hashlib

class NexaQuotaExceededError(Exception):
    pass

from .memory import global_memory
from .tools_registry import execute_tool
from .cache_manager import get_cache_manager, NexaCacheManager

class NexaAgent:
    def __init__(self, name: str, prompt: str = "", tools: List[Dict[str, Any]] = None, model: str = STRONG_MODEL, role: str = "", memory_scope: str = "local", protocol=None, max_tokens=None, stream=False, cache=False, max_history_turns=None, experience=None):
        self.name = name
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
        self.model = model
        if "/" in model:
            self.provider, self.model = model.split("/", 1)
            
        self.memory_scope = memory_scope
        # protocol 已在上面处理
        self.max_tokens = max_tokens
        self.stream = stream
        self.cache = cache
        self.max_history_turns = max_history_turns
        self.messages = []
        
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
            
        # Init Client - 使用新的 secrets API
        api_key, base_url = nexa_secrets.get_provider_config(self.provider)
        
        # 如果 provider 特定配置不存在，尝试通用配置
        if not api_key:
            api_key = nexa_secrets.get("API_KEY") or nexa_secrets.get("OPENAI_API_KEY")
        if not base_url:
            base_url = nexa_secrets.get("BASE_URL") or nexa_secrets.get("OPENAI_API_BASE")
        
        # Provider-specific defaults for base_url (if not configured)
        if not base_url:
            if self.provider == "deepseek":
                base_url = "https://api.deepseek.com/v1"
            elif self.provider == "minimax":
                base_url = "https://aihub.arcsysu.cn/v1"
            elif self.provider == "openai":
                base_url = "https://api.openai.com/v1"
            else:
                base_url = nexa_secrets.get("BASE_URL", "https://api.openai.com/v1")
        
        # 验证 API key 存在
        if not api_key:
            raise ValueError(
                f"API key not found for provider '{self.provider}'. "
                f"Please configure secrets.nxs with API_KEY or {self.provider.upper()}_API_KEY."
            )
                
        self.client = OpenAI(api_key=api_key, base_url=base_url)

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
                    summary_model = "deepseek-chat" if getattr(self, "provider", "default") == "deepseek" else ("gpt-4o-mini" if getattr(self, "provider", "default") == "default" else self.model)
                    
                    try:
                        summary_res = self.client.chat.completions.create(
                            model=summary_model,
                            messages=[{"role": "user", "content": sum_prompt}]
                        )
                        summary = summary_res.choices[0].message.content
                        self.messages = sys_msgs + [{"role": "system", "content": f"Previous conversation summary: {summary}"}] + self.messages[keep_idx:]
                    except Exception as e:
                        print(f"[{self.name} Context Compaction Failed]: {e}")

    def run(self, *args) -> str:
        user_input = " ".join([str(arg) for arg in args])
        
        # Pull context from memory if specified
        context = global_memory.get_context(self.memory_scope)
        if context:
            user_input += f"\n[Context]: {context}"
            
        print(f"\n> [{self.name} received]: {user_input}")
        self.messages.append({"role": "user", "content": user_input})
        
        self._compact_context()
        
        kwargs = {
            "model": self.model,
        }
        if self.max_tokens:
            kwargs["max_tokens"] = self.max_tokens
            
        if self.tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in self.tools]
            
        retries = 3
        # Tool Execution Loop
        while True:
            kwargs["messages"] = self.messages
            
            cached_result = self._check_cache(kwargs)
            if cached_result is not None:
                print(f"< [{self.name} replied from CACHE]: {cached_result}\n")
                self.messages.append({"role": "assistant", "content": cached_result})
                self._save_memory()
                return cached_result

            if self.stream and not self.tools and not self.protocol:
                kwargs["stream"] = True
                print(f"< [{self.name} replied]: ", end="")
                sys.stdout.flush()
                response = self.client.chat.completions.create(**kwargs)
                accumulated_reply = ""
                for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        sys.stdout.write(content)
                        sys.stdout.flush()
                        accumulated_reply += content
                print("\n")
                self.messages.append({"role": "assistant", "content": accumulated_reply})
                self._write_cache(kwargs, accumulated_reply)
                self._save_memory()
                return accumulated_reply
            
            # Non-streaming or Tool/Protocol mode
            if "stream" in kwargs:
                del kwargs["stream"]
                
            response = self.client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            
            if msg.tool_calls:
                msg_dict = msg.dict(exclude_none=True) if hasattr(msg, "dict") else dict(msg)
                self.messages.append(msg_dict)
                for tc in msg.tool_calls:
                    print(f"[{self.name} requested TOOL CALL]: {tc.function.name} -> {tc.function.arguments}")
                    result = execute_tool(tc.function.name, tc.function.arguments)
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": result
                    }
                    self.messages.append(tool_message)
                continue
            else:
                reply = msg.content or ""
                
                if self.protocol:
                    try:
                        parsed_reply = json.loads(reply)
                        # 验证并返回 Pydantic 模型实例
                        validated = self.protocol.model_validate(parsed_reply)
                        self.messages.append({"role": "assistant", "content": reply})
                        print(f"< [{self.name} replied (JSON)]: {reply}\n")
                        self._write_cache(kwargs, reply)
                        self._save_memory()
                        return validated  # 返回 Pydantic 模型实例，支持属性访问
                        
                    except Exception as e:
                        retries -= 1
                        if retries <= 0:
                            raise ValueError(f"Agent {self.name} failed to conform to protocol {self.protocol.__name__}: {str(e)}")
                        print(f"\n[{self.name} Schema Error, Retrying] {str(e)}")
                        self.messages.append({"role": "assistant", "content": reply})
                        self.messages.append({"role": "system", "content": f"Your last response failed schema validation. Please fix and return valid JSON. Error: {str(e)}"})
                        continue
                
                self.messages.append({"role": "assistant", "content": reply})
                print(f"< [{self.name} replied]: {reply}\n")
                self._write_cache(kwargs, reply)
                self._save_memory()
                return reply

    def clone(self, new_name: str, **kwargs):
        # 提取可以覆盖的属性
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
        
        return NexaAgent(
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
            max_history_turns=max_history_turns
        )

    def __rshift__(self, other):
        pass
