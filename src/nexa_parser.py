import re
from lark import Lark

nexa_grammar = """
program: import_stmt* script_stmt*

import_stmt: "include" STRING_LITERAL ";"

// v1.0.2: 添加语义类型声明支持
// v1.1: 渐进式类型系统 (Gradual Type System)
// P1-4: 内置 HTTP 服务器 (Built-In HTTP Server)
?script_stmt: tool_decl | agent_decl | flow_decl | protocol_decl | test_decl | type_decl | job_decl | server_decl | db_decl | auth_decl | kv_decl | concurrent_decl | defer_stmt | match_expr | struct_decl | enum_decl | trait_decl | impl_decl

// 语义类型定义: type Name = base_type @ "constraint"
type_decl: "type" IDENTIFIER "=" semantic_type

// P1-3: 后台任务系统 (Background Job System)
// job SendEmail on emails { perform(user_id) { ... } }
// job AnalyzeDoc on ai_tasks (retry: 2, timeout: 120) { perform(doc_id) { ... } on_failure(error, attempt) { ... } }
job_decl: "job" IDENTIFIER "on" STRING_LITERAL ["(" job_options ")"] "{" job_body "}"

job_options: job_option ("," job_option)*
job_option: IDENTIFIER "=" job_option_value

job_option_value: INT -> job_option_int
               | FLOAT -> job_option_float
               | STRING_LITERAL -> job_option_string
               | IDENTIFIER -> job_option_id

job_body: job_config* perform_decl [on_failure_decl]

job_config: IDENTIFIER ":" job_config_value

job_config_value: INT -> job_config_int_value
               | FLOAT -> job_config_float_value
               | STRING_LITERAL -> job_config_string_value
               | IDENTIFIER -> job_config_id_value

perform_decl: "perform" "(" job_param_list ")" block
            | "perform" "(" ")" block

job_param_list: IDENTIFIER ("," IDENTIFIER)*

on_failure_decl: "on_failure" "(" IDENTIFIER "," IDENTIFIER ")" block

// P1-4: Built-In HTTP Server (内置 HTTP 服务器)
// server 8080 { static "/assets" from "./public" cors { ... } middleware [mw1, mw2]
//   route GET "/chat" => ChatBot
//   route POST "/analyze" => DataExtractor |>> Analyzer |>> Reporter
//   semantic route "/help" => HelpBot
//   group "/admin" { middleware [require_admin] route GET "/" => AdminBot }
// }
server_decl: "server" INT "{" server_body "}"

// P1-5: Database Integration (内置数据库集成)
// db app_db = connect("sqlite://:memory:")
db_decl: "db" IDENTIFIER "=" "connect" "(" STRING_LITERAL ")"

// P2-1: Built-In Auth & OAuth (内置认证与 OAuth)
// auth myAuth = enable_auth("providers_json")
auth_decl: "auth" IDENTIFIER "=" "enable_auth" "(" STRING_LITERAL ")"

// P2-3: KV Store (内置键值存储)
kv_decl: "kv" IDENTIFIER "=" "open" "(" STRING_LITERAL ")"

// P2-2: Structured Concurrency (结构化并发)
// 独立表达式规则 (可同时用于语句级和表达式级)
spawn_expr: "spawn" "(" expression ")"
parallel_expr: "parallel" "(" expression ")"
race_expr: "race" "(" expression ")"
channel_expr: "channel" "(" ")"
after_expr: "after" "(" expression "," expression ")"
schedule_expr: "schedule" "(" expression "," expression ")"
select_expr: "select" "(" expression ["," expression] ")"

// 语句级并发声明 — 引用表达式规则
concurrent_decl: spawn_expr | parallel_expr | race_expr | channel_expr | after_expr | schedule_expr

server_body: server_directive* route_decl* server_group*

server_directive: "static" STRING_LITERAL "from" STRING_LITERAL     -> server_static
               | "cors" json_object                                   -> server_cors
               | "middleware" "[" identifier_list "]"                 -> server_middleware
               | "require_auth" STRING_LITERAL                        -> require_auth_decl

// route 声明: route GET "/path" => HandlerName
// 支持语义路由: semantic route "/path" => AgentName
route_decl: "semantic" "route" STRING_LITERAL "=>" route_handler     -> semantic_route_decl
          | "route" HTTP_METHOD STRING_LITERAL "=>" route_handler    -> route_decl_standard

// route handler: 函数名 / Agent名 / DAG chain
route_handler: IDENTIFIER                                           -> route_handler_fn
             | IDENTIFIER "|>>" IDENTIFIER ("|>>" IDENTIFIER)*      -> route_handler_dag

// HTTP 方法关键字
HTTP_METHOD: "GET" | "POST" | "PUT" | "DELETE" | "PATCH" | "HEAD" | "OPTIONS"

// server group: 路径前缀分组，带独立中间件
server_group: "group" STRING_LITERAL "{" server_directive* route_decl* "}"

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

// v1.1: 渐进式类型系统 - 完整类型表达式 (Type Expression)
// 支持: 基本类型、泛型(list/dict/Option/Result)、联合类型(|)、可选类型(?)
?type_expr: type_union_expr | type_non_union_expr

type_union_expr: type_non_union_expr ("|" type_non_union_expr)+ -> type_union_expr

?type_non_union_expr: type_compound_expr "?" -> type_option_expr
                    | type_compound_expr

?type_compound_expr: "str"   -> type_str_expr
                   | "int"   -> type_int_expr
                   | "float" -> type_float_expr
                   | "bool"  -> type_bool_expr
                   | "unit"  -> type_unit_expr
                   | "Option" "[" type_expr "]"  -> type_option_generic_expr
                   | "Result" "[" type_expr "," type_expr "]"  -> type_result_expr
                   | "list" "[" type_expr "]"   -> type_list_expr
                   | "dict" "[" type_expr "," type_expr "]"  -> type_dict_expr
                   | IDENTIFIER                   -> type_alias_expr

test_decl: "test" STRING_LITERAL block

tool_decl: "tool" IDENTIFIER "{" tool_body "}"
tool_body: tool_body_standard | tool_body_mcp | tool_body_python
tool_body_standard: "description" ":" STRING_LITERAL "," "parameters" ":" json_object
tool_body_mcp: "mcp" ":" STRING_LITERAL
tool_body_python: "python" ":" STRING_LITERAL

protocol_decl: "protocol" IDENTIFIER "{" protocol_body* "}"
protocol_body: IDENTIFIER ":" STRING_LITERAL ","?  -> protocol_body_string
              | IDENTIFIER ":" type_expr ","?       -> protocol_body_typed

json_object: "{" [json_pair ("," json_pair)*] "}"
json_pair: STRING_LITERAL ":" STRING_LITERAL

// Agent 修饰器支持: @limit, @timeout, @retry, @temperature
// Design by Contract: requires/ensures 契约条款放在签名后、函数体前
agent_decl: agent_decorator* "agent" IDENTIFIER ["->" return_type] ["uses" use_identifier_list] ["implements" IDENTIFIER] requires_clause* ensures_clause* "{" agent_property* "}"
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

// Design by Contract: flow 函数也支持 requires/ensures 契约
// v1.1: flow 支持返回类型标注 ["->" type_expr]
flow_decl: "flow" IDENTIFIER ["(" param_list ")"] ["->" type_expr] requires_clause* ensures_clause* block
param_list: param ("," param)*
param: IDENTIFIER ":" type_expr

// Design by Contract (契约式编程) - v1.1
// requires: 前置条件（确定性表达式或语义字符串）
// ensures: 后置条件（确定性表达式或语义字符串）
requires_clause: "requires" STRING_LITERAL -> requires_semantic_clause
               | "requires" comparison_expr -> requires_deterministic_clause

ensures_clause: "ensures" STRING_LITERAL -> ensures_semantic_clause
              | "ensures" comparison_expr -> ensures_deterministic_clause

block: "{" flow_stmt* "}"
semantic_if_block: "{" semantic_if_case* "}"
semantic_if_case: STRING_LITERAL "=>" expression ","?

// v1.0.1-beta: 扩展 flow_stmt 支持传统控制流和 Python 逃生舱
// v1.2: 新增 try_assignment_stmt / otherwise_assignment_stmt / try_expr_stmt
// P3-5: 新增 defer_stmt (延迟执行)
?flow_stmt: try_assignment_stmt        // v1.2: x = expr? 错误传播
           | otherwise_assignment_stmt  // v1.2: x = expr otherwise handler
           | assignment_stmt
           | try_expr_stmt              // v1.2: expr? 错误传播（无赋值）
           | expr_stmt
           | semantic_if_stmt
           | traditional_if_stmt    // 新增: 传统 if/else if/else
           | foreach_stmt           // 新增: for each 循环
           | while_stmt             // 新增: while 循环
           | loop_stmt
           | match_stmt
           | match_expr             // P3-3: match expression with pattern matching
           | let_pattern_stmt       // P3-3: let destructuring
           | for_pattern_stmt       // P3-3: for destructuring
           | assert_stmt
           | try_catch_stmt
           | print_stmt
           | break_stmt
           | continue_stmt          // 新增: continue
           | python_escape_stmt     // 新增: Python 逃生舱
           | defer_stmt             // P3-5: defer 延迟执行

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

// P3-5: Defer Statement (延迟执行) — defer expr; 在作用域退出时 LIFO 执行
defer_stmt: "defer" expression ";"

// P3-4: ADT - Struct/Trait/Enum (代数数据类型)
// struct Point { x: Int, y: Int }
struct_decl: "struct" IDENTIFIER "{" struct_field ("," struct_field)* "}"
struct_field: IDENTIFIER [":" IDENTIFIER]

// enum Option { Some(value), None }
enum_decl: "enum" IDENTIFIER "{" enum_variant ("," enum_variant)* "}"
enum_variant: IDENTIFIER ["(" IDENTIFIER ("," IDENTIFIER)* ")"]

// trait Printable { fn format() -> String }
trait_decl: "trait" IDENTIFIER "{" trait_method ("," trait_method)* "}"
trait_method: "fn" IDENTIFIER "(" [simple_param_list] ")" [":" IDENTIFIER]

// impl Printable for Point { fn format() -> String { ... } }
impl_decl: "impl" IDENTIFIER "for" IDENTIFIER "{" impl_method ("," impl_method)* "}"
impl_method: "fn" IDENTIFIER "(" [simple_param_list] ")" block

// Simple param list for trait/impl methods (just identifiers, no types)
simple_param_list: IDENTIFIER ("," IDENTIFIER)*

// v1.2: Error Propagation — ? 操作符和 otherwise 内联错误处理
// x = expr?         → try_assignment_stmt (错误传播，失败时 early-return)
// x = expr otherwise handler → otherwise_assignment_stmt (内联错误处理)
// expr?             → try_expr_stmt (错误传播，无赋值)
try_assignment_stmt: IDENTIFIER "=" expression "?" ";?"
otherwise_assignment_stmt: IDENTIFIER "=" expression "otherwise" otherwise_handler ";?"
try_expr_stmt: expression "?" ";?"

// otherwise handler: 可以是 Agent 调用、表达式值、变量、代码块
otherwise_handler: method_call           -> otherwise_agent_handler
                 | STRING_LITERAL        -> otherwise_value_handler
                 | IDENTIFIER            -> otherwise_var_handler
                 | block                 -> otherwise_block_handler

assignment_stmt: IDENTIFIER "=" expression ";"?
               | IDENTIFIER "=" match_stmt
               | IDENTIFIER "=" match_expr
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

// P3-3: Pattern Matching + Destructuring (模式匹配 + 解构)
// match expr { pattern => body, pattern => body if guard, ... }
match_expr: "match" expression "{" match_arm ("," match_arm)* [","] "}"

match_arm: pattern "=>" (expression | block) ["if" expression]  // guard condition optional

// Pattern types (7 types, aligned with NTNT)
?pattern: wildcard_pattern | literal_pattern | variable_pattern
        | tuple_pattern | array_pattern | map_pattern | variant_pattern

wildcard_pattern: "_" -> wildcard_pat

literal_pattern: INT -> literal_int_pat
               | FLOAT -> literal_float_pat
               | STRING_LITERAL -> literal_str_pat
               | "true" -> literal_true_pat
               | "false" -> literal_false_pat

variable_pattern: IDENTIFIER -> variable_pat

tuple_pattern: "(" pattern ("," pattern)+ ")" -> tuple_pat

array_pattern: "[" pattern ("," pattern)* "]" -> array_pat
             | "[" pattern ("," pattern)* ".." IDENTIFIER "]" -> array_pat_rest

map_pattern: "{" [map_pattern_entry ("," map_pattern_entry)*] "}" -> map_pat
             | "{" map_pattern_entry ("," map_pattern_entry)* ".." IDENTIFIER "}" -> map_pat_rest
map_pattern_entry: IDENTIFIER [":" pattern] -> map_entry_pat

variant_pattern: IDENTIFIER "::" IDENTIFIER ["(" pattern ("," pattern)* ")"] -> variant_pat

// Let destructuring: let (a, b) = expr
let_pattern_stmt: "let" pattern "=" expression ";"

// For destructuring: for (key, value) in items
for_pattern_stmt: "for" pattern "in" expression block

// DAG 表达式支持: 分叉(|>>, ||)、合流(&>>, &&)、管道(>>)、条件分支(??)
// 支持链式调用: expr |>> [A, B] &>> C
// P3-2/P3-6: 新增 pipe_expr 和 null_coalesce_expr
?expression: pipe_expr | null_coalesce_expr | fallback_expr | pipeline_expr | dag_expr | base_expr

// P3-2: Pipe Operator (管道操作符) — x |> f desugars to f(x)
pipe_expr: base_expr ("|>" base_expr)+ -> pipe_chain_expr

// P3-6: Null Coalescing (空值合并) — expr ?? fallback
null_coalesce_expr: base_expr ("??" base_expr)+ -> null_coalesce_expr

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
// DAG 条件分支使用 "??" 字面量（与 null_coalesce_expr 的 "??" 共享同一匿名终端）
dag_branch_expr: base_expr "??" base_expr ":" base_expr
               | base_expr "??" semantic_if_block
               | pipeline_expr "??" semantic_if_block

// 管道表达式
pipeline_expr: base_expr (">>" base_expr)+

// 列表表达式转换为identifier列表
identifier_list_as_expr: "[" identifier_list "]"

// P3-4: Variant call expression — Option::Some(42) as expression (not just pattern)
variant_call_expr: IDENTIFIER "::" IDENTIFIER ["(" argument_list ")"]

// P3-4: Field init argument — Point(x: 1, y: 2) uses IDENTIFIER ":" expression
field_init: IDENTIFIER ":" expression

// v1.0.1-beta: base_expr 支持更多字面量类型
?base_expr: join_call
          | method_call
          | img_call
          | property_access
          | std_call
          | binary_expr
          | comparison_expr
          | semantic_if_expr
          | spawn_expr
          | parallel_expr
          | race_expr
          | channel_expr
          | after_expr
          | select_expr
          | template_expr
          | variant_call_expr
          | STRING_LITERAL -> string_expr
          | MULTILINE_STRING -> multiline_string_expr
          | INT -> int_expr
          | FLOAT -> float_expr
          | "true" -> true_expr
          | "false" -> false_expr
          | IDENTIFIER -> id_expr
          | dict_access_expr

// P2-4: Template System (模板系统)
// template + TEMPLATE_STRING -- explicit prefix for template strings
template_expr: "template" TEMPLATE_STRING -> template_string_expr

// semantic_if 表达式形式: semantic_if (var, "condition") { "case1" => action1 }
semantic_if_expr: "semantic_if" "(" IDENTIFIER "," STRING_LITERAL ")" semantic_if_block

dict_access_expr: base_expr "[" expression "]"
property_access: IDENTIFIER "." IDENTIFIER | property_access "." IDENTIFIER

std_call: "std" "." IDENTIFIER "." IDENTIFIER "(" [argument_list] ")"

join_call: "join" "(" identifier_list ")" [ "." IDENTIFIER "(" [argument_list] ")" ]

method_call: IDENTIFIER ("." IDENTIFIER)? "(" [argument_list] ")"
img_call: "img" "(" STRING_LITERAL ")"
?argument: expression | kwarg | field_init
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
IDENTIFIER: /(?!if\b|else\b|for\b|each\b|in\b|while\b|break\b|continue\b|agent\b|tool\b|flow\b|protocol\b|test\b|match\b|loop\b|until\b|print\b|try\b|catch\b|assert\b|true\b|false\b|join\b|std\b|img\b|requires\b|ensures\b|invariant\b|type\b|unit\b|otherwise\b|job\b|on\b|perform\b|on_failure\b|server\b|group\b|route\b|serve\b|static\b|cors\b|semantic\b|GET\b|POST\b|PUT\b|DELETE\b|PATCH\b|HEAD\b|OPTIONS\b|db\b|connect\b|query\b|execute\b|auth\b|require_auth\b|enable_auth\b|oauth\b|kv\b|open\b|spawn\b|parallel\b|race\b|channel\b|after\b|schedule\b|await\b|select\b|recv\b|send\b|close\b|sleep_ms\b|template\b|defer\b|struct\b|enum\b|trait\b|impl\b|fn\b|let\b)[a-zA-Z_][a-zA-Z0-9_]*/
STRING_LITERAL: /"[^"]*"/
MULTILINE_STRING: /\"\"\"([^\""]|\"{1,2}([^\""]|$))*?\"\"\"/
// P2-4: Template string token (same regex as MULTILINE_STRING, but used with "template" prefix)
TEMPLATE_STRING: /\"\"\"([^\""]|\"{1,2}([^\""]|$))*?\"\"\"/
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

def extract_implements_annotations(text):
    """
    从 Nexa 源代码中提取 @implements 和 @supports 注解
    
    这些注解使用注释格式 (// @implements: feature.id)，Lark 会忽略注释，
    因此需要预处理提取。
    
    Returns:
        list of dicts: [{"feature_id": "...", "supports_id": "...", "agent_name": "...", "line": N}, ...]
    """
    annotations = []
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        # 提取 @implements 注解
        impl_match = re.search(r'//\s*@implements\s*:\s*([\w.]+)', line)
        if impl_match:
            feature_id = impl_match.group(1)
            # 查找对应的 agent 名称（通常在下一行或同一行）
            agent_name = _find_agent_near_line(lines, i)
            annotations.append({
                "type": "ImplementsAnnotation",
                "feature_id": feature_id,
                "agent_name": agent_name,
                "line": i + 1,
                "annotation_type": "implements"
            })
        
        # 提取 @supports 注解
        support_match = re.search(r'//\s*@supports\s*:\s*([\w.]+)', line)
        if support_match:
            constraint_id = support_match.group(1)
            agent_name = _find_agent_near_line(lines, i)
            annotations.append({
                "type": "SupportsAnnotation",
                "constraint_id": constraint_id,
                "agent_name": agent_name,
                "line": i + 1,
                "annotation_type": "supports"
            })
    
    return annotations


def _find_agent_near_line(lines, annotation_line):
    """在注解行附近查找 agent 名称"""
    # 查找当前行和后续几行中的 agent 关键字
    for j in range(annotation_line, min(annotation_line + 3, len(lines))):
        agent_match = re.search(r'agent\s+(\w+)', lines[j])
        if agent_match:
            return agent_match.group(1)
    # 查找前一行
    if annotation_line > 0:
        agent_match = re.search(r'agent\s+(\w+)', lines[annotation_line - 1])
        if agent_match:
            return agent_match.group(1)
    return "unknown"


def parse(text):
    """解析 Nexa 源代码文本并返回 AST (字典格式)"""
    from src.ast_transformer import NexaTransformer
    parser = get_parser()
    tree = parser.parse(text)
    # 使用转换器将 Lark Tree 转换为字典格式的 AST
    transformer = NexaTransformer()
    ast = transformer.transform(tree)
    
    # 提取 @implements/@supports 注解并附加到 AST
    annotations = extract_implements_annotations(text)
    if annotations:
        ast["annotations"] = annotations
    
    return ast

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
