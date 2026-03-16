from typing import Any, Dict, List
from .core import client, STRONG_MODEL
from .secrets import nexa_secrets
from openai import OpenAI
import json

class NexaQuotaExceededError(Exception):
    pass

from .memory import global_memory
from .tools_registry import execute_tool

class NexaAgent:
    def __init__(self, name: str, prompt: str = "", tools: List[Dict[str, Any]] = None, model: str = STRONG_MODEL, role: str = "", memory_scope: str = "local", protocol=None, max_tokens=None):
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
        self.messages = []
        if self.system_prompt:
            self.messages.append({"role": "system", "content": self.system_prompt})
            
        # Init Client
        api_key = nexa_secrets.get(f"{self.provider.upper()}_API_KEY")
        base_url = nexa_secrets.get(f"{self.provider.upper()}_BASE_URL")
        
        # Fallbacks for existing environment
        if not api_key:
            # Fallback to the one in core.py or default
            api_key = nexa_secrets.get("OPENAI_API_KEY") or "sk-lDc9yRMvfPzpxXKuuXB2LA"
            
        if not base_url:
            if self.provider == "deepseek":
                base_url = "https://api.deepseek.com/v1"
            elif self.provider == "minimax":
                base_url = "https://aihub.arcsysu.cn/v1"
            else:
                base_url = "https://api.openai.com/v1"
                
        self.client = OpenAI(api_key=api_key, base_url=base_url)


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
        if self.tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in self.tools]
            
        # Tool Execution Loop
        while True:
            kwargs["messages"] = self.messages
            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            
            if msg.tool_calls:
                # Need to append the assistant's request to the thread
                self.messages.append(msg)
                
                for tc in msg.tool_calls:
                    print(f"[{self.name} requested TOOL CALL]: {tc.function.name} -> {tc.function.arguments}")
                    # Execute tool locally
                    result = execute_tool(tc.function.name, tc.function.arguments)
                    
                    # Append tool result
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": result
                    }
                    self.messages.append(tool_message)
                
                # Continue loop to send tool results back to LLM
            else:
                reply = msg.content or ""
                
                if self.protocol:
                    try:
                        parsed_reply = json.loads(reply)
                        self.protocol.model_validate(parsed_reply) # throws if invalid
                        
                        self.messages.append({"role": "assistant", "content": reply})
                        print(f"< [{self.name} replied (JSON)]: {reply}\n")
                        return reply
                        
                    except Exception as e:
                        retries -= 1
                        if retries <= 0:
                            raise ValueError(f"Agent {self.name} failed to conform to protocol {self.protocol.__name__}: {str(e)}")
                        print(f"\n[91m[{self.name} Schema Error, Retrying] {str(e)}[0m")
                        self.messages.append({"role": "assistant", "content": reply})
                        self.messages.append({"role": "system", "content": f"Your last response failed schema validation. Please fix and return valid JSON. Error: {str(e)}"})
                        continue
                
                self.messages.append({"role": "assistant", "content": reply})
                print(f"< [{self.name} replied]: {reply}\n")
                return reply

    def __rshift__(self, other):
        pass
