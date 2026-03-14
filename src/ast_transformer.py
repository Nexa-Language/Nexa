from lark import Transformer, v_args
import json

class NexaTransformer(Transformer):
    """
    负责将 Lark 解析后生成的树结构（Tree）转化为 
    Nexa 原生的轻量级 JSON / Dict 抽象语法树（AST）
    """
    @v_args(inline=False)
    def program(self, args):
        return {"type": "Program", "body": args}

    @v_args(inline=False)
    def tool_decl(self, args):
        name = str(args[0])
        body_args = args[1]
        return {
            "type": "ToolDeclaration",
            "name": name,
            "description": body_args["description"],
            "parameters": body_args["parameters"]
        }

    @v_args(inline=False)
    def tool_body(self, args):
        return {
            "description": str(args[0]).strip('"'),
            "parameters": args[1]
        }

    @v_args(inline=False)
    def json_object(self, args):
        obj = {}
        for pair in args:
            obj[pair[0]] = pair[1]
        return obj

    @v_args(inline=True)
    def json_pair(self, k, v):
        return (str(k).strip('"'), str(v).strip('"'))

    @v_args(inline=False)
    def agent_decl(self, args):
        # args can contain: name, -> return_type (optional), uses list (optional), agent_properties...
        name = str(args[0])
        return_type = "str"
        uses = []
        properties = {}
        
        for arg in args[1:]:
            if isinstance(arg, dict) and arg.get("type") == "return_type":
                return_type = arg["value"]
            elif isinstance(arg, list) and len(arg) > 0 and isinstance(arg[0], str): # This might conflict with array values
                # Actually, how do we distinguish uses list? The grammar says:
                # agent_decl: "agent" IDENTIFIER ["->" return_type] ["uses" identifier_list] "{" agent_property* "}"
                # Let's just iterate and check types
                if not isinstance(arg, dict):
                    uses = arg
            elif isinstance(arg, dict) and "key" in arg:
                properties[arg["key"]] = arg["value"]
                
        return {
            "type": "AgentDeclaration",
            "name": name,
            "return_type": return_type,
            "uses": uses,
            "properties": properties,
            "prompt": properties.get("prompt", "")
        }

    @v_args(inline=False)
    def return_type(self, args):
        val = "".join([str(a) for a in args])
        return {"type": "return_type", "value": val}

    @v_args(inline=False)
    def agent_property(self, args):
        key = str(args[0])
        value = args[1]
        return {"key": key, "value": value}

    @v_args(inline=True)
    def string_val(self, s):
        return str(s).strip('"')

    @v_args(inline=True)
    def id_val(self, i):
        return str(i)

    @v_args(inline=True)
    def list_val(self, i):
        return i

    @v_args(inline=False)
    def identifier_list(self, args):
        return [str(arg) for arg in args]

    @v_args(inline=False)
    def flow_decl(self, args):
        return {
            "type": "FlowDeclaration",
            "name": str(args[0]),
            "body": args[1]
        }

    @v_args(inline=False)
    def block(self, args):
        return args

    @v_args(inline=False)
    def assignment_stmt(self, args):
        return {
            "type": "AssignmentStatement",
            "target": str(args[0]),
            "value": args[1]
        }

    @v_args(inline=False)
    def expr_stmt(self, args):
        return {
            "type": "ExpressionStatement",
            "expression": args[0]
        }

    @v_args(inline=False)
    def semantic_if_stmt(self, args):
        condition = str(args[0]).strip('"')
        target = str(args[1])
        consequence = args[2]
        alternative = args[3] if len(args) > 3 else []
        
        return {
            "type": "SemanticIfStatement",
            "condition": condition,
            "target_variable": target,
            "consequence": consequence,
            "alternative": alternative
        }

    @v_args(inline=False)
    def loop_stmt(self, args):
        return {
            "type": "LoopUntilStatement",
            "body": args[0],
            "condition": args[1]
        }

    @v_args(inline=False)
    def match_stmt(self, args):
        target = str(args[0])
        cases = []
        default_case = None
        for arg in args[1:]:
            if arg["type"] == "MatchCase":
                cases.append(arg)
            elif arg["type"] == "DefaultCase":
                default_case = arg
        
        return {
            "type": "MatchIntentStatement",
            "target": target,
            "cases": cases,
            "default": default_case
        }

    @v_args(inline=False)
    def match_case(self, args):
        return {
            "type": "MatchCase",
            "intent": str(args[0]).strip('"'),
            "expression": args[1]
        }

    @v_args(inline=False)
    def default_case(self, args):
        return {
            "type": "DefaultCase",
            "expression": args[0]
        }

    @v_args(inline=False)
    def pipeline_expr(self, args):
        return {
            "type": "PipelineExpression",
            "stages": args
        }

    @v_args(inline=False)
    def join_call(self, args):
        # join_call: "join" "(" identifier_list ")" [ "." IDENTIFIER "(" [argument_list] ")" ]
        agents = args[0]
        method = "run"
        arguments = []
        if len(args) > 1:
            method = str(args[1])
            if len(args) > 2:
                arguments = args[2]
        
        return {
            "type": "JoinCallExpression",
            "agents": agents,
            "method": method,
            "arguments": arguments
        }

    @v_args(inline=False)
    def method_call(self, args):
        arguments = []
        if len(args) > 2:
            arguments = args[2]
        return {
            "type": "MethodCallExpression",
            "object": str(args[0]),
            "method": str(args[1]),
            "arguments": arguments
        }

    @v_args(inline=False)
    def argument_list(self, args):
        return args

    @v_args(inline=True)
    def string_expr(self, s):
        return {"type": "StringLiteral", "value": str(s).strip('"')}

    @v_args(inline=True)
    def id_expr(self, i):
        return {"type": "Identifier", "value": str(i)}


if __name__ == "__main__":
    from nexa_parser import parse
    import os
    
    example_path = os.path.join(os.path.dirname(__file__), '../examples/01_hello_world.nx')
    with open(example_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    print("\n" + "="*50)
    print("🛡️ [Nexa Transformer] Starting AST Generation...")
    print("="*50)
    
    tree = parse(code)
    transformer = NexaTransformer()
    ast = transformer.transform(tree)
    
    # 强制在终端输出美化后的结构
    print("\n🟢 AST Generated Successfully! Dump:\n")
    print(json.dumps(ast, indent=2, ensure_ascii=False))
    print("="*50)
