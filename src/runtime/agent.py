from typing import Any, Dict, List
from .core import client, STRONG_MODEL
from .secrets import nexa_secrets
from openai import OpenAI
import json
import os
import sys

class NexaQuotaExceededError(Exception):
    pass

from .memory import global_memory
from .tools_registry import execute_tool

class NexaAgent:
    def __init__(self, name: str, prompt: str = "", tools: List[Dict[str, Any]] = None, model: str = STRONG_MODEL, role: str = "", memory_scope: str = "local", protocol=None, max_tokens=None, stream=False):
        self.name = name
        self.system_prompt = prompt
        if role:
            self.system_prompt = f"Role: {role}. {self.system_prompt}".strip()
        self.tools = tools or []
        
        self.provider = "default"
        self.model = model
        if "/" in model:
            self.provider, self.model = model.split("/", 1)
            
        self.memory_scope = memory_scope
        self.protocol = protocol
        self.max_tokens = max_tokens
        self.stream = stream
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
            
        # Init Client
        api_key = nexa_secrets.get(f"{self.provider.upper()}_API_KEY")
        base_url = nexa_secrets.get(f"{self.provider.upper()}_BASE_URL")
        
        # Fallbacks for existing environment
        if not api_key:
            api_key = "sk-lDc9yRMvfPzpxXKuuXB2LA" if self.provider in ["minimax", "deepseek"] else (nexa_secrets.get("OPENAI_API_KEY") or "sk-lDc9yRMvfPzpxXKuuXB2LA")
            
        if not base_url:
            if self.provider == "deepseek":
                base_url = "https://api.deepseek.com/v1"
            elif self.provider == "minimax":
                base_url = "https://aihub.arcsysu.cn/v1"
            else:
                base_url = "https://api.openai.com/v1"
                
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _save_memory(self):
        if self.memory_file:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.messages, f, ensure_ascii=False, indent=2)

    def run(self, *args) -> str:
        user_input = " ".join([str(arg) for arg in args])
        
        # Pull context from memory if specified
        context = global_memory.get_context(self.memory_scope)
        if context:
            user_input += f"\n[Context]: {context}"
            
        print(f"\n> [{self.name} received]: {user_input}")
        self.messages.append({"role": "user", "content": user_input})
        
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
                        self.protocol.model_validate(parsed_reply)
                        self.messages.append({"role": "assistant", "content": reply})
                        print(f"< [{self.name} replied (JSON)]: {reply}\n")
                        self._save_memory()
                        return reply
                        
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
        
        return NexaAgent(
            name=new_name,
            prompt=prompt,
            tools=tools,
            model=model,
            role=role,
            memory_scope=memory_scope,
            protocol=protocol,
            max_tokens=max_tokens,
            stream=stream
        )

    def __rshift__(self, other):
        pass
