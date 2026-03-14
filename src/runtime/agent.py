from typing import Any, Dict, List
from .core import client, STRONG_MODEL
from .memory import global_memory
from .tools_registry import execute_tool

class NexaAgent:
    def __init__(self, name: str, prompt: str = "", tools: List[Dict[str, Any]] = None, model: str = STRONG_MODEL, role: str = "", memory_scope: str = "local"):
        self.name = name
        self.system_prompt = prompt
        if role:
            self.system_prompt = f"Role: {role}. {self.system_prompt}".strip()
        self.tools = tools or []
        self.model = model
        self.memory_scope = memory_scope
        self.messages = []
        if self.system_prompt:
            self.messages.append({"role": "system", "content": self.system_prompt})

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
                self.messages.append({"role": "assistant", "content": reply})
                print(f"< [{self.name} replied]: {reply}\n")
                return reply

    def __rshift__(self, other):
        pass
