from lark import Lark

nexa_grammar = """
program: script_stmt*

?script_stmt: tool_decl | agent_decl | flow_decl

tool_decl: "tool" IDENTIFIER "{" tool_body "}"
tool_body: "description" ":" STRING_LITERAL "," "parameters" ":" json_object
json_object: "{" [json_pair ("," json_pair)*] "}"
json_pair: STRING_LITERAL ":" STRING_LITERAL

agent_decl: "agent" IDENTIFIER ["uses" identifier_list] "{" agent_body "}"
identifier_list: IDENTIFIER ("," IDENTIFIER)*
agent_body: "prompt" ":" STRING_LITERAL

flow_decl: "flow" IDENTIFIER block

block: "{" flow_stmt* "}"

?flow_stmt: assignment_stmt | expr_stmt | semantic_if_stmt

assignment_stmt: IDENTIFIER "=" expression ";"
expr_stmt: expression ";"

semantic_if_stmt: "semantic_if" STRING_LITERAL "against" IDENTIFIER block ["else" block]

?expression: method_call 
           | STRING_LITERAL -> string_expr 
           | IDENTIFIER -> id_expr

method_call: IDENTIFIER "." IDENTIFIER "(" [argument_list] ")"
argument_list: expression ("," expression)*

IDENTIFIER: /[a-zA-Z_][a-zA-Z0-9_]*/
STRING_LITERAL: /"[^"]*"/

%import common.WS
%import common.C_COMMENT
%import common.CPP_COMMENT
%ignore WS
%ignore C_COMMENT
%ignore CPP_COMMENT
"""

def get_parser():
    """初始化并返回 Lark 解析器实例"""
    return Lark(nexa_grammar, start='program', parser='earley')

def parse(text):
    """解析 Nexa 源代码文本并返回 AST"""
    parser = get_parser()
    return parser.parse(text)

if __name__ == "__main__":
    import os
    example_path = os.path.join(os.path.dirname(__file__), '../examples/01_hello_world.nx')
    with open(example_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    print("\n" + "="*50)
    print("🚀 [Nexa Parser] Starting Syntax Analysis...")
    print("="*50)
    
    try:
        tree = parse(code)
        print("\n✅ Parsing Successful! Displaying Raw Syntax Tree:\n")
        print(tree.pretty())
        print("="*50)
    except Exception as e:
        print("\n❌ Parsing Failed! Error Details:\n")
        print(e)
        print("="*50)
