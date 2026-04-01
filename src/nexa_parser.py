from lark import Lark

nexa_grammar = """
program: import_stmt* script_stmt*

import_stmt: "include" STRING_LITERAL ";"

// v1.0.2: 添加语义类型声明支持
?script_stmt: tool_decl | agent_decl | flow_decl | protocol_decl | test_decl | type_decl

// 语义类型定义: type Name = base_type @ "constraint"
type_decl: "type" IDENTIFIER "=" semantic_type

semantic_type: base_type "@" STRING_LITERAL  -> constrained_type
             | base_type                       -> simple_type

// 内置类型关键字优先匹配（优先级高于 IDENTIFIER）
// Lark 会按顺序匹配，关键字优先于 IDENTIFIER
base_type: "str"   -> str_type
         | "int"   -> int_type
         | "float" -> float_type
         | "bool"  -> bool_type
         | "list" "[" inner_type "]"   -> list_type
         | "dict" "[" inner_type "," inner_type "]"  -> dict_type
         | IDENTIFIER                   -> custom_type

// 内部类型用于泛型参数（递归支持嵌套类型）
?inner_type: "str"   -> str_type
           | "int"   -> int_type
           | "float" -> float_type
           | "bool"  -> bool_type
           | IDENTIFIER -> custom_type

test_decl: "test" STRING_LITERAL block

tool_decl: "tool" IDENTIFIER "{" tool_body "}"
tool_body: tool_body_standard | tool_body_mcp | tool_body_python
tool_body_standard: "description" ":" STRING_LITERAL "," "parameters" ":" json_object
tool_body_mcp: "mcp" ":" STRING_LITERAL
tool_body_python: "python" ":" STRING_LITERAL

protocol_decl: "protocol" IDENTIFIER "{" protocol_body* "}"
protocol_body: IDENTIFIER ":" STRING_LITERAL ","?

json_object: "{" [json_pair ("," json_pair)*] "}"
json_pair: STRING_LITERAL ":" STRING_LITERAL

// Agent 修饰器支持: @limit, @timeout, @retry, @temperature
agent_decl: agent_decorator* "agent" IDENTIFIER ["->" return_type] ["uses" use_identifier_list] ["implements" IDENTIFIER] "{" agent_property* "}"
agent_decorator: "@" agent_decorator_name "(" agent_decorator_params ")"
agent_decorator_name: "limit" | "timeout" | "retry" | "temperature"
agent_decorator_params: agent_decorator_param ("," agent_decorator_param)*
agent_decorator_param: IDENTIFIER "=" (INT | FLOAT)
return_type: IDENTIFIER "<" IDENTIFIER ">" | IDENTIFIER

agent_property: IDENTIFIER ":" agent_property_value ","?
 ?agent_property_value: STRING_LITERAL -> string_val
                      | MULTILINE_STRING -> multiline_string_val
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

// v1.0.1-beta: 扩展 flow_stmt 支持传统控制流和 Python 逃生舱
?flow_stmt: assignment_stmt
          | expr_stmt
          | semantic_if_stmt
          | traditional_if_stmt    // 新增: 传统 if/else if/else
          | foreach_stmt           // 新增: for each 循环
          | while_stmt             // 新增: while 循环
          | loop_stmt
          | match_stmt
          | assert_stmt
          | try_catch_stmt
          | print_stmt
          | break_stmt
          | continue_stmt          // 新增: continue
          | python_escape_stmt     // 新增: Python 逃生舱

// break 语句 - 用于循环中断
break_stmt: "break" ";"

// continue 语句 - 用于循环跳过
continue_stmt: "continue" ";"

// 传统 if/else if/else 语句 (确定性条件分支) - v1.0.1-beta
// 使用 ~ 进行贪婪匹配（Lark 的 + 量词是贪婪的）
traditional_if_stmt: "if" "(" traditional_condition ")" block ("else" "if" "(" traditional_condition ")" block)+ ("else" block)?
                   | "if" "(" traditional_condition ")" block "else" block
                   | "if" "(" traditional_condition ")" block

// 简化版 if (无 else if 链)
simple_if_stmt: "if" "(" traditional_condition ")" block
// 条件表达式支持逻辑运算符 and/or
traditional_condition: logical_expr
logical_expr: comparison_expr (("and" | "or") comparison_expr)*

// 比较表达式 - 使用 CMP_OP 终端确保多字符操作符优先匹配
comparison_expr: expression CMP_OP expression
               | expression  // 简单布尔判断

// for each 循环 - 数组/集合遍历
foreach_stmt: "for" "each" IDENTIFIER "in" expression block
            | "for" "each" IDENTIFIER "," IDENTIFIER "in" expression block  // 带索引

// while 循环 - 确定性条件循环
while_stmt: "while" "(" traditional_condition ")" block

// Python 逃生舱 - 使用 python! 关键字后跟多行字符串
python_escape_stmt: "python!" MULTILINE_STRING

// 保留原有 if_stmt 兼容性 (简化版)
if_stmt: "if" "(" condition ")" block ["else" block]
condition: expression CMP_OP expression
print_stmt: "print" "(" expression ")" ";"?

try_catch_stmt: "try" block "catch" "(" IDENTIFIER ")" block
assert_stmt: "assert" expression ";"

assignment_stmt: IDENTIFIER "=" expression ";"?
               | IDENTIFIER "=" match_stmt
expr_stmt: expression ";"?

// semantic_if 支持两种语法:
// 1. 原有语法: semantic_if "condition" fast_match r"pattern" against var { ... }
// 2. 简化语法: semantic_if (var, "condition") { "case1" => action1, "case2" => action2 }
semantic_if_stmt: "semantic_if" STRING_LITERAL ["fast_match" (STRING_LITERAL | REGEX_LITERAL)] "against" IDENTIFIER block ["else" block]
               | "semantic_if" "(" IDENTIFIER "," STRING_LITERAL ")" semantic_if_block

loop_stmt: "loop" block "until" "(" expression ")"

match_stmt: "match" IDENTIFIER "{" match_case* default_case? "}"
match_case: "intent" "(" STRING_LITERAL ")" "=>" expression ","?
default_case: "_" "=>" expression ","?

// DAG 表达式支持: 分叉(|>>, ||)、合流(&>>, &&)、管道(>>)、条件分支(??)
// 支持链式调用: expr |>> [A, B] &>> C
?expression: fallback_expr | pipeline_expr | dag_expr | base_expr

fallback_expr: base_expr "fallback" expression

// DAG 操作符 - 从左到右结合，支持链式调用
dag_expr: dag_chain_expr | dag_fork_expr | dag_merge_expr | dag_branch_expr | dag_fire_forget | dag_consensus

// 链式 DAG 表达式: 支持 expr |>> [...] &>> Agent 或 expr |>> [...] >> Agent
dag_chain_expr: dag_fork_expr dag_chain_tail
             | dag_fork_expr (">>" base_expr)+

dag_chain_tail: ("&>>" | "&&") base_expr
             | ("&>>" | "&&") base_expr (">>" base_expr)*

// 分叉表达式:
// - expr |>> [Agent1, Agent2, ...] - 并行执行，等待所有结果
// - expr || [Agent1, Agent2, ...] - 并行执行，不等待结果 (fire-and-forget)
// 使用 -> 显式命名规则来区分操作符
dag_fork_expr: base_expr "|>>" identifier_list_as_expr -> dag_fork_wait
             | base_expr "||" identifier_list_as_expr -> dag_fork_fire_forget

// 合流表达式:
// - [Agent1, Agent2] &>> MergerAgent - 顺序合流
// - [Agent1, Agent2] && MergerAgent - 共识合流
dag_merge_expr: identifier_list_as_expr ("&>>" | "&&") base_expr

// Fire-and-forget 独立表达式
dag_fire_forget: base_expr "||" identifier_list_as_expr

// 共识合流独立表达式
dag_consensus: identifier_list_as_expr "&&" base_expr

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

// v1.0.1-beta: base_expr 支持更多字面量类型
?base_expr: join_call
          | method_call
          | img_call
          | property_access
          | std_call
          | binary_expr
          | comparison_expr
          | semantic_if_expr
          | STRING_LITERAL -> string_expr
          | MULTILINE_STRING -> multiline_string_expr
          | INT -> int_expr
          | FLOAT -> float_expr
          | "true" -> true_expr
          | "false" -> false_expr
          | IDENTIFIER -> id_expr
          | dict_access_expr

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

// v1.0.1-beta: 二元运算符扩展 (支持加减乘除取模)
binary_expr: base_expr BINARY_OP base_expr

// v1.0.1-beta: 操作符终端定义 (确保正确匹配)
CMP_OP: ">=" | "<=" | "==" | "!=" | ">" | "<"
BINARY_OP: "+" | "-" | "*" | "/" | "%"

// v1.0.1-beta: 声明关键字优先级
%declare ELSE

// v1.0.1-beta: IDENTIFIER 定义
// 使用负向断言确保关键字不会被当作标识符匹配
// 注意：使用 \b 边界确保只排除完整关键字，不排除前缀匹配如 test_xxx
IDENTIFIER: /(?!if\b|else\b|for\b|each\b|in\b|while\b|break\b|continue\b|agent\b|tool\b|flow\b|protocol\b|test\b|match\b|loop\b|until\b|print\b|try\b|catch\b|assert\b|true\b|false\b|join\b|std\b|img\b)[a-zA-Z_][a-zA-Z0-9_]*/
STRING_LITERAL: /"[^"]*"/
MULTILINE_STRING: /\"\"\"([^\""]|\"{1,2}([^\""]|$))*?\"\"\"/
REGEX_LITERAL: /r"[^"]*"/

// Python 逃生舱定界符 - 使用安全定界符避免 Markdown 和大括号冲突
// 匹配 <|python|> 和 <|end|> 之间的所有内容（使用非贪婪匹配）
PYTHON_ESCAPE_OPEN: /<\|python\|>/
PYTHON_ESCAPE_CLOSE: /<\|end\|>/

%import common.INT
%import common.FLOAT
%import common.WS
%import common.C_COMMENT
%import common.CPP_COMMENT
%ignore WS
%ignore C_COMMENT
%ignore CPP_COMMENT
"""

def get_parser():
    """初始化并返回 Lark 解析器实例"""
    # 使用 Earley 解析器处理歧义语法，transformer 中会选择优先分支
    return Lark(nexa_grammar, start='program', parser='earley', ambiguity='explicit')

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
