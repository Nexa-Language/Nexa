import re

with open('src/runtime/agent.py', 'r') as f:
    content = f.read()

# Add imports
if "from .secrets import nexa_secrets" not in content:
    content = content.replace("from .core import client, STRONG_MODEL", "from .core import client, STRONG_MODEL\nfrom .secrets import nexa_secrets\nfrom openai import OpenAI\nimport json\n\nclass NexaQuotaExceededError(Exception):\n    pass\n")

# Modify __init__
init_old = """    def __init__(self, name: str, prompt: str = "", tools: List[Dict[str, Any]] = None, model: str = STRONG_MODEL, role: str = "", memory_scope: str = "local"):
        self.name = name
        self.system_prompt = prompt
        if role:
            self.system_prompt = f"Role: {role}. {self.system_prompt}".strip()
        self.tools = tools or []
        self.model = model
        self.memory_scope = memory_scope
        self.messages = []
        if self.system_prompt:
            self.messages.append({"role": "system", "content": self.system_prompt})"""

init_new = """    def __init__(self, name: str, prompt: str = "", tools: List[Dict[str, Any]] = None, model: str = STRONG_MODEL, role: str = "", memory_scope: str = "local", protocol=None, max_tokens=None):
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
"""
content = content.replace(init_old, init_new)

# Modify run method
run_old = """        kwargs = {
            "model": self.model,
        }
        if self.tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in self.tools]
        
        # Tool Execution Loop
        while True:
            kwargs["messages"] = self.messages
            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message"""

run_new = """        kwargs = {
            "model": self.model,
        }
        if self.max_tokens:
            kwargs["max_tokens"] = self.max_tokens
            
        if self.tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in self.tools]
            
        if self.protocol:
            kwargs["response_format"] = {"type": "json_object"}
            self.messages.append({"role": "system", "content": f"You MUST output valid JSON conforming exactly to this JSON Schema:\n{json.dumps(self.protocol.model_json_schema())}"})
            
        retries = 3
        
        # Tool Execution Loop
        while True:
            kwargs["messages"] = self.messages
            
            try:
                response = self.client.chat.completions.create(**kwargs)
            except Exception as e:
                if "max_tokens" in str(e).lower() or "limit" in str(e).lower():
                    raise NexaQuotaExceededError(f"Model {self.model} exceeded quota: {str(e)}")
                raise e
                
            # Emulate limit exception for testing if usage > max_tokens manually (some APIs don't throw, just truncate)
            if self.max_tokens and response.usage and response.usage.total_tokens > self.max_tokens:
                raise NexaQuotaExceededError(f"Token limit exceeded! Used {response.usage.total_tokens}, max allowed is {self.max_tokens}")
                
            if response.choices[0].finish_reason == "length":
                raise NexaQuotaExceededError(f"Token limit exceeded! Hit max_tokens limit of {self.max_tokens}")

            msg = response.choices[0].message"""

content = content.replace(run_old, run_new)

# Modify end of run
end_old = """            else:
                reply = msg.content or ""
                self.messages.append({"role": "assistant", "content": reply})
                print(f"< [{self.name} replied]: {reply}\\n")
                return reply"""

end_new = """            else:
                reply = msg.content or ""
                
                if self.protocol:
                    try:
                        parsed_reply = json.loads(reply)
                        self.protocol.model_validate(parsed_reply) # throws if invalid
                        
                        self.messages.append({"role": "assistant", "content": reply})
                        print(f"< [{self.name} replied (JSON)]: {reply}\\n")
                        return reply
                        
                    except Exception as e:
                        retries -= 1
                        if retries <= 0:
                            raise ValueError(f"Agent {self.name} failed to conform to protocol {self.protocol.__name__}: {str(e)}")
                        print(f"\\n\033[91m[{self.name} Schema Error, Retrying] {str(e)}\033[0m")
                        self.messages.append({"role": "assistant", "content": reply})
                        self.messages.append({"role": "system", "content": f"Your last response failed schema validation. Please fix and return valid JSON. Error: {str(e)}"})
                        continue
                
                self.messages.append({"role": "assistant", "content": reply})
                print(f"< [{self.name} replied]: {reply}\\n")
                return reply"""

content = content.replace(end_old, end_new)

with open('src/runtime/agent.py', 'w') as f:
    f.write(content)
