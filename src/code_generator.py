# 此文件由 Nexa v0.5 Code Generator 自动生成
import os
import json
import pydantic
from src.runtime.stdlib import STD_NAMESPACE_MAP

BOILERPLATE = """# 此文件由 Nexa v0.5 Code Generator 自动生成
import os
import json
import pydantic
from src.runtime.stdlib import STD_NAMESPACE_MAP
from src.runtime.agent import NexaAgent
from src.runtime.evaluator import nexa_semantic_eval, nexa_intent_routing
from src.runtime.orchestrator import join_agents, nexa_pipeline
from src.runtime.memory import global_memory
from src.runtime.stdlib import STD_TOOLS_SCHEMA, STD_NAMESPACE_MAP
from src.runtime.secrets import nexa_secrets

# ==========================================
# [Target Code] 自动生成的编排逻辑
# ==========================================
"""

class CodeGenerator:
    """
    负责将 Nexa AST 转换为等价执行逻辑的 Python 代码
    """
    def __init__(self, ast):
        self.ast = ast
        self.code = [BOILERPLATE]
        self.indent_level = 0
        
        self.protocols = []
        self.tools = []
        self.agents = []
        self.flows = []
        
    def _indent(self):
        return "    " * self.indent_level
        
    def generate(self):
        for node in self.ast.get("body", []):
            if node["type"] == "ProtocolDeclaration":
                self.protocols.append(node)
            elif node["type"] == "ToolDeclaration":
                self.tools.append(node)
            elif node["type"] == "AgentDeclaration":
                self.agents.append(node)
            elif node["type"] == "FlowDeclaration":
                self.flows.append(node)

        self._generate_protocols()
        self._generate_tools()
        self._generate_agents()
        self._generate_flows()
        
        self.code.append("if __name__ == \"__main__\":")
        self.code.append("    flow_main()")
        self.code.append("")
        
        return "\n".join(self.code)

    def _generate_protocols(self):
        for proto in self.protocols:
            name = proto["name"]
            self.code.append(f'class {name}(pydantic.BaseModel):')
            for f_name, f_type in proto["fields"].items():
                py_type = "str"
                if f_type == "int": py_type = "int"
                if f_type == "float": py_type = "float"
                if f_type == "bool": py_type = "bool"
                self.code.append(f'    {f_name}: {py_type}')
            self.code.append('')

    def _generate_tools(self):
        for tool in self.tools:
            name = tool["name"]
            desc = tool["description"]
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
            prompt = agent.get("prompt", "")
            uses = agent.get("uses", [])
            properties = agent.get("properties", {})
            model = properties.get("model", '"minimax-m2.5"').strip('"')
            role = properties.get("role", '""').strip('"')
            memory_scope = properties.get("memory", '"local"').strip('"')
            
            tool_refs_list = []
            for t in uses:
                if t.startswith("std."):
                    if t in STD_NAMESPACE_MAP:
                        for fn_name in STD_NAMESPACE_MAP[t]:
                            tool_refs_list.append(f"STD_TOOLS_SCHEMA['{fn_name}']")
                    else:
                        print(f"⚠️ Warning: Unknown standard namespace '{t}'")
                else:
                    tool_refs_list.append(f"__tool_{t}_schema")
            tool_refs = ", ".join(tool_refs_list)
            implements = agent.get("implements")
            max_tokens = agent.get("max_tokens")
            
            self.code.append(f'{name} = NexaAgent(')
            self.code.append(f'    name="{name}",')
            self.code.append(f'    prompt="{prompt}",')
            self.code.append(f'    model="{model}",')
            self.code.append(f'    role="{role}",')
            self.code.append(f'    memory_scope="{memory_scope}",')
            if implements:
                self.code.append(f'    protocol={implements},')
            if max_tokens:
                self.code.append(f'    max_tokens={max_tokens},')
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
        st_type = stmt.get("type")
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
            self.code.append(f"{self._indent()}if nexa_semantic_eval(\"{cond}\", {target}):")
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

        elif st_type == "MatchIntentStatement":
            target = stmt["target"]
            intents = [case["intent"] for case in stmt["cases"]]
            intents_str = "[ " + ", ".join([f'"{i}"' for i in intents]) + "]"
            
            self.code.append(f"{self._indent()}__matched_intent = nexa_intent_routing({intents_str}, {target})")
            for i, case in enumerate(stmt["cases"]):
                if i == 0:
                    self.code.append(f"{self._indent()}if __matched_intent == \"{case['intent']}\":")
                else:
                    self.code.append(f"{self._indent()}elif __matched_intent == \"{case['intent']}\":")
                
                self.indent_level += 1
                self._generate_statement({"type": "ExpressionStatement", "expression": case["expression"]})
                self.indent_level -= 1
                
            if stmt.get("default"):
                self.code.append(f"{self._indent()}else:")
                self.indent_level += 1
                self._generate_statement({"type": "ExpressionStatement", "expression": stmt["default"]["expression"]})
                self.indent_level -= 1

        elif st_type == "LoopUntilStatement":
            self.code.append(f"{self._indent()}while True:")
            self.indent_level += 1
            for sub_stmt in stmt["body"]:
                self._generate_statement(sub_stmt)
            cond_str = self._resolve_expression(stmt["condition"])
            self.code.append(f"{self._indent()}if nexa_semantic_eval({cond_str}, str(locals())):")
            self.indent_level += 1
            self.code.append(f"{self._indent()}break")
            self.indent_level -= 2
            self.code.append(f"")

    def _resolve_expression(self, expr):
        ex_type = expr.get("type")
        if ex_type == "StringLiteral":
            return f'"{expr["value"]}"'
        elif ex_type == "SecretCall":
            return f'nexa_secrets.get("{expr["key"]}")'
        elif ex_type == "Identifier":
            return expr["value"]
        elif ex_type == "MethodCallExpression":
            obj = expr["object"]
            method = expr["method"]
            args_str = ", ".join([self._resolve_expression(a) for a in expr.get("arguments", [])])
            return f'{obj}.{method}({args_str})'
        elif ex_type == "PipelineExpression":
            initial_call = self._resolve_expression(expr["stages"][0])
            agent_names = []
            for stage in expr["stages"][1:]:
                if stage["type"] == "Identifier":
                    agent_names.append(stage["value"])
                elif stage["type"] == "MethodCallExpression":
                    agent_names.append(stage["object"]) # just the agent name for now.
            agents_list_str = "[ " + ", ".join(agent_names) + " ]"
            return f"nexa_pipeline({initial_call}, {agents_list_str})"
        elif ex_type == "JoinCallExpression":
            agents_list_str = "[ " + ", ".join([a for a in expr["agents"]]) + "]"
            method = expr.get("method")
            if "arguments" in expr:
                args_str = ", ".join([self._resolve_expression(a) for a in expr.get("arguments", [])])
            else:
                args_str = "''"
                
            join_str = f"join_agents({agents_list_str}, {args_str})"
            if method:
                return f"{method}.run({join_str})"
            return join_str
            
        return "None"

if __name__ == "__main__":
    import sys
    from src.nexa_parser import parse
    from src.ast_transformer import NexaTransformer
    
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        src = f.read()
    
    tree = parse(src)
    transformer = NexaTransformer()
    ast = transformer.transform(tree)
    
    generator = CodeGenerator(ast)
    print(generator.generate())
