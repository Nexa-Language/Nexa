import json

BOILERPLATE = """# 此文件由 Nexa v0.1 Code Generator 自动生成
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
        print(f"\\n> [{self.name} received]: {user_input}")
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
        print(f"< [{self.name} replied]: {reply}\\n")
        return reply

# ==========================================
# [Target Code] 用户代码转译结果
# ==========================================
"""

class CodeGenerator:
    """
    负责将 Nexa AST 转换为等价执行逻辑的 Python 代码
    并注入运行时所需的重试和判定拦截机制
    """
    def __init__(self, ast):
        self.ast = ast
        self.code = [BOILERPLATE]
        self.indent_level = 0
        
        # 为了保证先后声明，收集 tools, agents 和 flows
        self.tools = []
        self.agents = []
        self.flows = []
        
    def _indent(self):
        return "    " * self.indent_level
        
    def generate(self):
        for node in self.ast.get("body", []):
            if node["type"] == "ToolDeclaration":
                self.tools.append(node)
            elif node["type"] == "AgentDeclaration":
                self.agents.append(node)
            elif node["type"] == "FlowDeclaration":
                self.flows.append(node)

        self._generate_tools()
        self._generate_agents()
        self._generate_flows()
        
        # 补全入口代码
        self.code.append("if __name__ == \"__main__\":")
        self.code.append("    flow_main()")
        self.code.append("")
        
        return "\n".join(self.code)

    def _generate_tools(self):
        for tool in self.tools:
            name = tool["name"]
            desc = tool["description"]
            # parameters in python
            props = ",\n        ".join([f'"{k}": {{"type": "{v}"}}' for k, v in tool["parameters"].items()])
            reqs = ", ".join([f'"{k}"' for k in tool["parameters"].keys()])
            
            tool_code = f"""__tool_{name}_schema = {{
    "name": "{name}",
    "description": "{desc}",
    "parameters": {{
        "type": "object",
        "properties": {{
            {props}
        }},
        "required": [{reqs}]
    }}
}}
"""
            self.code.append(tool_code)

    def _generate_agents(self):
        for agent in self.agents:
            name = agent["name"]
            prompt = agent["prompt"]
            uses = agent["uses"]
            
            tool_refs = ", ".join([f"__tool_{t}_schema" for t in uses])
            self.code.append(f'{name} = __NexaAgent(')
            self.code.append(f'    name="{name}",')
            self.code.append(f'    prompt="{prompt}",')
            self.code.append(f'    tools=[{tool_refs}]')
            self.code.append(f')\n')
            
    def _generate_flows(self):
        for flow in self.flows:
            name = flow["name"]
            self.code.append(f'def flow_{name}():')
            self.indent_level += 1
            for stmt in flow["body"]:
                self._generate_statement(stmt)
            self.indent_level -= 1
            self.code.append("")

    def _generate_statement(self, stmt):
        st_type = stmt["type"]
        if st_type == "AssignmentStatement":
            target = stmt["target"]
            val_str = self._resolve_expression(stmt["value"])
            self.code.append(f"{self._indent()}{target} = {val_str}")
            
        elif st_type == "ExpressionStatement":
            val_str = self._resolve_expression(stmt["expression"])
            self.code.append(f"{self._indent()}{val_str}")
            
        elif st_type == "SemanticIfStatement":
            cond = stmt["condition"]
            target = stmt["target_variable"]
            self.code.append(f"{self._indent()}if __nexa_semantic_eval(\"{cond}\", {target}):")
            self.indent_level += 1
            for sub_stmt in stmt.get("consequence", []):
                 self._generate_statement(sub_stmt)
            self.indent_level -= 1
            
            alt = stmt.get("alternative", [])
            if alt:
                self.code.append(f"{self._indent()}else:")
                self.indent_level += 1
                for sub_stmt in alt:
                    self._generate_statement(sub_stmt)
                self.indent_level -= 1

    def _resolve_expression(self, expr):
        ex_type = expr["type"]
        if ex_type == "StringLiteral":
            return f'"{expr["value"]}"'
        elif ex_type == "Identifier":
            return expr["value"]
        elif ex_type == "MethodCallExpression":
            obj = expr["object"]
            method = expr["method"]
            args_str = ", ".join([self._resolve_expression(a) for a in expr.get("arguments", [])])
            return f'{obj}.{method}({args_str})'
        return "None"

if __name__ == "__main__":
    from nexa_parser import parse
    from ast_transformer import NexaTransformer
    import os
    
    print("\n" + "="*50)
    print("✨ [Nexa Code Generator] Starting End-to-End Pipeline...")
    print("="*50)
    
    example_path = os.path.join(os.path.dirname(__file__), '../examples/01_hello_world.nx')
    with open(example_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # 1. Parse
    tree = parse(code)
    # 2. Transform
    ast = NexaTransformer().transform(tree)
    # 3. Generate
    gen = CodeGenerator(ast)
    python_code = gen.generate()
    
    # Output to File
    out_path = os.path.join(os.path.dirname(__file__), '../examples/out_hello_world.py')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(python_code)
        
    print(f"\n✅ Python Code Generated Successfully to: {out_path}\n")
    print("📜 预览前 60 行代码:\n")
    print("\n".join(python_code.split("\n")[:60]))
    print("...\n" + "="*50)
