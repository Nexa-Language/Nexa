import re

with open('src/ast_transformer.py', 'r') as f:
    content = f.read()

agent_decl_new = """    @v_args(inline=False)
    def agent_decl(self, args):
        max_tokens = None
        if args[0] is not None:
            max_tokens = int(args[0].value)
            
        name = str(args[1])
        
        return_type = "str"
        if args[2] is not None:
            return_type = args[2]["value"] if isinstance(args[2], dict) else "str"
            
        uses = []
        if args[3] is not None:
            uses = args[3]
            
        implements = None
        if args[4] is not None:
            implements = str(args[4])
            
        properties = {}
        for arg in args[5:]:
            if isinstance(arg, dict) and "key" in arg:
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

with open('src/ast_transformer.py', 'w') as f:
    f.write(content)
