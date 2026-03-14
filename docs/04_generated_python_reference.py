# 此文件由 Nexa v0.1 转译器生成 (Reference Implementation)
# 源文件: examples/01_hello_world.nx

import os
import json
from typing import Any, Dict, List
from openai import OpenAI
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ==========================================
# 0. Nexa 编译器注入的底层 Runtime (Boilerplate)
# ==========================================
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
    resp = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Evaluate condition against target text. Condition: {condition}"},
            {"role": "user", "content": str(target_text)}
        ],
        response_format=SemanticEvalSchema,
        timeout=10.0
    )
    return resp.choices[0].message.parsed.matched

def __nexa_semantic_eval(condition: str, target_text: str) -> bool:
    try:
        return __nexa_semantic_eval_with_retry(condition, target_text)
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
        # 将所有参数转化为用户输入字符串
        user_input = " ".join([str(arg) for arg in args])
        self.messages.append({"role": "user", "content": user_input})
        
        # 实际情况中，这里会有完善的 tool execution 循环。
        # v0.1 Reference 简化仅做调用展示。
        kwargs = {
            "model": "gpt-4o",
            "messages": self.messages,
        }
        if self.tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in self.tools]
            # (在此处理工具调用的循环...)

        response = client.chat.completions.create(**kwargs)
        reply = response.choices[0].message.content or ""
        self.messages.append({"role": "assistant", "content": reply})
        return reply

# ==========================================
# 1. 解析目标：Tool 映射
# ==========================================
# tool web_search 
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
# 注意：v0.1 转译后，开发者需要手动在这里或者外围实现 def web_search(query): 及其派发逻辑。

# ==========================================
# 2. 解析目标：Agent 映射
# ==========================================
# agent Researcher uses web_search { prompt: ... }
Researcher = __NexaAgent(
    name="Researcher",
    prompt="You are a brilliant researcher. Answer the query context based on the web search results.",
    tools=[__tool_web_search_schema]
)

# ==========================================
# 3. 解析目标：Flow 映射执行
# ==========================================
def flow_main():
    # result = Researcher.run("Search the latest news about the new 'Nexa' programming language.");
    result = Researcher.run("Search the latest news about the new 'Nexa' programming language.")
    
    # semantic_if "..." against result
    if __nexa_semantic_eval("The result explicitly mentions 'agent-native' or 'transpiler'", result):
        # Researcher.run("Provide a 50-word technical summary based on the result.", result);
        Researcher.run("Provide a 50-word technical summary based on the result.", result)
    else:
        # Researcher.run("Just reply: 'No relevant Nexa logic found in search results.'");
        Researcher.run("Just reply: 'No relevant Nexa logic found in search results.'")

if __name__ == "__main__":
    flow_main()
