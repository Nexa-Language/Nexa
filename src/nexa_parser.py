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
                     | "[" fallback_list "]" -> fallback_list_val
                     | INT -> int_val
                     | "true" -> true_val
                     | "false" -> false_val

fallback_list: fallback_item ("," fallback_item)*
fallback_item: STRING_LITERAL -> primary_model
              | "fallback" ":" STRING_LITERAL -> fallback_model

identifier_list: IDENTIFIER ("," IDENTIFIER)*
use_identifier_list: use_identifier ("," use_identifier)*
use_identifier: IDENTIFIER | IDENTIFIER "." IDENTIFIER -> namespaced_id
              | STRING_LITERAL -> string_use
              | "mcp:" STRING_LITERAL -> mcp_use

flow_decl: "flow" IDENTIFIER ["(" param_list ")"] block
param_list: param ("," param)*
param: IDENTIFIER ":" IDENTIFIER

block: "{" flow_stmt* "}"
semantic_if_block: "{" semantic_if_case* "}"
semantic_if_case: STRING_LITERAL "=>" expression ","?

?flow_stmt: assignment_stmt | expr_stmt | semantic_if_stmt | loop_stmt | match_stmt | assert_stmt | try_catch_stmt | print_stmt | if_stmt

// 传统 if 语句
if_stmt: "if" "(" condition ")" block ["else" block]
condition: expression comparison_op expression
comparison_op: "==" | "!=" | "<" | ">" | "<=" | ">="
print_stmt: "print" "(" expression ")" ";"?

try_catch_stmt: "try" block "catch" "(" IDENTIFIER ")" block
assert_stmt: "assert" expression ";"

assignment_stmt: IDENTIFIER "=" expression ";"?
               | IDENTIFIER "=" match_stmt
expr_stmt: expression ";"?

// semantic_if 支持两种语法:
// 1. 原有语法: semantic_if "condition" fast_match:"pattern" against var { ... }
// 2. 简化语法: semantic_if (var, "condition") { "case1" => action1, "case2" => action2 }
semantic_if_stmt: "semantic_if" STRING_LITERAL ["fast_match" ":" STRING_LITERAL] "against" IDENTIFIER block ["else" block]
               | "semantic_if" "(" IDENTIFIER "," STRING_LITERAL ")" semantic_if_block

loop_stmt: "loop" block "until" "(" expression ")"

match_stmt: "match" IDENTIFIER "{" match_case* default_case? "}"
match_case: "intent" "(" STRING_LITERAL ")" "=>" expression ","?
default_case: "_" "=>" expression ","?

// DAG 表达式支持: 分叉(|>>)、合流(&>>)、管道(>>)、条件分支(??)
// 支持链式调用: expr |>> [A, B] &>> C
?expression: fallback_expr | pipeline_expr | dag_expr | base_expr

fallback_expr: base_expr "fallback" expression

// DAG 操作符 - 从左到右结合，支持链式调用
dag_expr: dag_chain_expr | dag_fork_expr | dag_merge_expr | dag_branch_expr

// 链式 DAG 表达式: 支持 expr |>> [...] &>> Agent
dag_chain_expr: dag_fork_expr "&>>" base_expr

// 分叉表达式: expr |>> [Agent1, Agent2, ...] 
dag_fork_expr: base_expr "|>>" identifier_list_as_expr

// 合流表达式: [Agent1, Agent2] &>> MergerAgent
dag_merge_expr: identifier_list_as_expr "&>>" base_expr

// 条件分支表达式:
// 1. 简单形式: expr ?? TrueAgent : FalseAgent
// 2. 块形式: expr ?? { "case1" => action1, "case2" => action2 }
// 3. 管道后分支: expr >> Agent ?? { ... }
dag_branch_expr: base_expr "??" base_expr ":" base_expr
              | base_expr "??" semantic_if_block
              | pipeline_expr "??" semantic_if_block

// 管道表达式
pipeline_expr: base_expr (">>" base_expr)+

// 列表表达式转换为identifier列表
identifier_list_as_expr: "[" identifier_list "]"

?base_expr: join_call
          | method_call
          | img_call
          | property_access
          | std_call
          | binary_expr
          | comparison_expr
          | semantic_if_expr
          | STRING_LITERAL -> string_expr
          | IDENTIFIER -> id_expr
          | dict_access_expr

// 比较表达式
comparison_expr: expression comparison_op expression

// semantic_if 表达式形式: semantic_if (var, "condition") { "case1" => action1 }
semantic_if_expr: "semantic_if" "(" IDENTIFIER "," STRING_LITERAL ")" semantic_if_block

dict_access_expr: base_expr "[" expression "]"
property_access: IDENTIFIER "." IDENTIFIER | property_access "." IDENTIFIER

std_call: "std" "." IDENTIFIER "." IDENTIFIER "(" [argument_list] ")"

join_call: "join" "(" identifier_list ")" [ "." IDENTIFIER "(" [argument_list] ")" ]

method_call: IDENTIFIER ("." IDENTIFIER)? "(" [argument_list] ")"
img_call: "img" "(" STRING_LITERAL ")"
?argument: expression | kwarg
kwarg: IDENTIFIER "=" expression
argument_list: argument ("," argument)*

// 二元运算符 (字符串拼接等)
binary_expr: base_expr ("+" base_expr)+

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
    """解析 Nexa 源代码文本并返回 AST (字典格式)"""
    from src.ast_transformer import NexaTransformer
    parser = get_parser()
    tree = parser.parse(text)
    # 使用转换器将 Lark Tree 转换为字典格式的 AST
    transformer = NexaTransformer()
    return transformer.transform(tree)

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
