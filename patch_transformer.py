import re

with open('src/ast_transformer.py', 'r') as f:
    content = f.read()

# Add Protocol Transformer
protocol_methods = """
    @v_args(inline=False)
    def protocol_decl(self, args):
        name = str(args[0])
        fields = {}
        for arg in args[1:]:
            if isinstance(arg, dict) and arg.get("type") == "ProtocolBody":
                fields[arg["key"]] = arg["value"]
        return {
            "type": "ProtocolDeclaration",
            "name": name,
            "fields": fields
        }

    @v_args(inline=False)
    def protocol_body(self, args):
        key = str(args[0])
        value = str(args[1]).strip('"')
        return {
            "type": "ProtocolBody",
            "key": key,
            "value": value
        }
"""
content = "".join([content.split("@v_args(inline=False)\n    def json_object")[0], protocol_methods, "\n    @v_args(inline=False)\n    def json_object", content.split("@v_args(inline=False)\n    def json_object")[1]])

# update agent_decl
agent_decl_new = """    @v_args(inline=False)
    def agent_decl(self, args):
        max_tokens = None
        args_idx = 0
        if isinstance(args[args_idx], lark.lexer.Token) and args[args_idx].type == "INT":
            max_tokens = int(args[args_idx].value)
            args_idx += 1
            
        name = str(args[args_idx])
        args_idx += 1
        
        return_type = "str"
        uses = []
        implements = None
        properties = {}
        
        for arg in args[args_idx:]:
            if isinstance(arg, dict) and arg.get("type") == "return_type":
                return_type = arg["value"]
            elif isinstance(arg, list) and len(arg) > 0 and isinstance(arg[0], str):
                uses = arg
            elif isinstance(arg, lark.lexer.Token):
                if implements is None:
                    implements = str(arg)
            elif isinstance(arg, str):
                implements = str(arg)
            elif isinstance(arg, dict) and "key" in arg:
                properties[arg["key"]] = arg["value"]
                
        return {
            "type": "AgentDeclaration",
            "name": name,
            "max_tokens": max_tokens,
            "return_type": return_type,
            "uses": uses,
            "implements": implements,
            "properties": properties,
            "prompt": properties.get("prompt", "")
        }"""
content = re.sub(r'    @v_args\(inline=False\)\s+def agent_decl\(self, args\):.*?return \{\s+"type": "AgentDeclaration".*?\}', agent_decl_new, content, flags=re.DOTALL)
content = "import lark\n" + content
with open('src/ast_transformer.py', 'w') as f:
    f.write(content)
