# 此文件由 Nexa v0.1 Code Generator 自动生成
import os
import json
from typing import Any, Dict, List
from openai import OpenAI
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ==========================================
# [Boilerplate] Nexa 核心运行时环境
# ==========================================
client = OpenAI(
    base_url="https://aihub.arcsysu.cn/v1",
    api_key="sk-lDc9yRMvfPzpxXKuuXB2LA"
)

class SemanticEvalSchema(BaseModel):
    matched: bool = Field(description="Whether the condition is matched.")
    confidence: float = Field(description="Confidence from 0.0 to 1.0.")

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def __nexa_semantic_eval_with_retry(condition: str, target_text: str) -> bool:
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"Evaluate condition against target text. Condition: {condition} - Respond EXACTLY with a JSON object like {{'matched': bool, 'confidence': float}}."},
            {"role": "user", "content": str(target_text)}
        ],
        response_format={"type": "json_object"},
        timeout=10.0
    )
    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
        return bool(data.get("matched", False))
    except Exception:
        return False

def __nexa_semantic_eval(condition: str, target_text: str) -> bool:
    print(f"[Semantic_IF Evaluating] Condition: '{condition}'")
    try:
        matched = __nexa_semantic_eval_with_retry(condition, target_text)
        print(f"[Semantic_IF Result] -> {matched}")
        return matched
    except Exception as e:
        print(f"[Nexa Runtime Warning] Semantic eval failed after retries: {e}. Defaulting to False.")
        return False

class __NexaAgent:
    def __init__(self, name: str, prompt: str, tools: List[Dict[str, Any]]):
        self.name = name
        self.system_prompt = prompt
        self.tools = tools
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def run(self, *args) -> str:
        user_input = " ".join([str(arg) for arg in args])
        print(f"\n> [{self.name} received]: {user_input}")
        self.messages.append({"role": "user", "content": user_input})
        
        kwargs = {
            "model": "minimax-m2.5",
            "messages": self.messages,
        }
        if self.tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in self.tools]

        response = client.chat.completions.create(**kwargs)
        
        msg = response.choices[0].message
        reply = msg.content or ""
        
        if getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                print(f"[{self.name} requested TOOL CALL]: {tc.function.name} -> {tc.function.arguments}")
                reply += f" [Tool Call: {tc.function.name}({tc.function.arguments})] "

        self.messages.append({"role": "assistant", "content": reply})
        print(f"< [{self.name} replied]: {reply}\n")
        return reply

# ==========================================
# [Target Code] 用户代码转译结果
# ==========================================

__tool_web_search_schema = {
    "name": "web_search",
    "description": "Search the web for a given query string.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"}
        },
        "required": ["query"]
    }
}

Researcher = __NexaAgent(
    name="Researcher",
    prompt="You are a brilliant researcher. Answer the query context based on the web search results.",
    tools=[__tool_web_search_schema]
)

def flow_main():
    result = Researcher.run("Search the latest news about the new 'Nexa' programming language.")
    if __nexa_semantic_eval("The result explicitly mentions 'agent-native' or 'transpiler'", result):
        Researcher.run("Provide a 50-word technical summary based on the result.", result)
    else:
        Researcher.run("Just reply: 'No relevant Nexa logic found in search results.'")

if __name__ == "__main__":
    flow_main()
