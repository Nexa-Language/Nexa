from lark import Lark

nexa_grammar = """
program: import_stmt* script_stmt*

import_stmt: "include" STRING_LITERAL ";"

?script_stmt: tool_decl | agent_decl | flow_decl | protocol_decl | test_decl

test_decl: "test" STRING_LITERAL block

tool_decl: "tool" IDENTIFIER "{" tool_body "}"
tool_body: "description" ":" STRING_LITERAL "," "parameters" ":" json_object

protocol_decl: "protocol" IDENTIFIER "{" protocol_body* "}"
protocol_body: IDENTIFIER ":" STRING_LITERAL ","?

json_object: "{" [json_pair ("," json_pair)*] "}"
json_pair: STRING_LITERAL ":" STRING_LITERAL

agent_decl: ["@" "limit" "(" "max_tokens" "=" INT ")"] "agent" IDENTIFIER ["->" return_type] ["uses" use_identifier_list] ["implements" IDENTIFIER] "{" agent_property* "}"
return_type: IDENTIFIER "<" IDENTIFIER ">" | IDENTIFIER

agent_property: IDENTIFIER ":" agent_property_value ","?
?agent_property_value: STRING_LITERAL -> string_val
                     | IDENTIFIER -> id_val
                     | "[" identifier_list "]" -> list_val

identifier_list: IDENTIFIER ("," IDENTIFIER)*
use_identifier_list: use_identifier ("," use_identifier)*
use_identifier: IDENTIFIER | IDENTIFIER "." IDENTIFIER -> namespaced_id
              | STRING_LITERAL -> string_use
              | "mcp:" STRING_LITERAL -> mcp_use

flow_decl: "flow" IDENTIFIER block

block: "{" flow_stmt* "}"

?flow_stmt: assignment_stmt | expr_stmt | semantic_if_stmt | loop_stmt | match_stmt | assert_stmt | try_catch_stmt

try_catch_stmt: "try" block "catch" "(" IDENTIFIER ")" block
assert_stmt: "assert" expression ";"

assignment_stmt: IDENTIFIER "=" expression ";"
               | IDENTIFIER "=" match_stmt
expr_stmt: expression ";"

semantic_if_stmt: "semantic_if" STRING_LITERAL ["fast_match" ":" STRING_LITERAL] "against" IDENTIFIER block ["else" block]

loop_stmt: "loop" block "until" "(" expression ")"

match_stmt: "match" IDENTIFIER "{" match_case* default_case? "}"
match_case: "intent" "(" STRING_LITERAL ")" "=>" expression ","?
default_case: "_" "=>" expression ","?

?expression: fallback_expr | pipeline_expr | base_expr

fallback_expr: base_expr "fallback" expression

pipeline_expr: base_expr (">>" base_expr)+

?base_expr: join_call 
          | method_call 
          | img_call
          | property_access
          | STRING_LITERAL -> string_expr 
          | IDENTIFIER -> id_expr
          | dict_access_expr

dict_access_expr: base_expr "[" expression "]"
property_access: IDENTIFIER "." IDENTIFIER | property_access "." IDENTIFIER

join_call: "join" "(" identifier_list ")" [ "." IDENTIFIER "(" [argument_list] ")" ]

method_call: IDENTIFIER ("." IDENTIFIER)? "(" [argument_list] ")"
img_call: "img" "(" STRING_LITERAL ")"
?argument: expression | kwarg
kwarg: IDENTIFIER "=" expression
argument_list: argument ("," argument)*

IDENTIFIER: /[a-zA-Z_][a-zA-Z0-9_]*/
STRING_LITERAL: /"[^"]*"/

%import common.INT
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
    import sys
    example_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '../examples/01_hello_world.nx')
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
