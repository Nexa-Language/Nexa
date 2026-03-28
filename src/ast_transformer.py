import lark
from lark import Transformer, v_args
import json

class NexaTransformer(Transformer):
    """
    负责将 Lark 解析后生成的树结构（Tree）转化为 
    Nexa 原生的轻量级 JSON / Dict 抽象语法树（AST）
    """
    @v_args(inline=False)
    def import_stmt(self, args):
        return {"type": "IncludeStatement", "path": str(args[0]).strip('"')}

    @v_args(inline=False)
    def fallback_expr(self, args):
        primary = args[0]
        backup = args[1]
        
        if hasattr(primary, 'data'):
            primary = getattr(self, primary.data)(primary.children)
            
        if hasattr(backup, 'data'):
            backup = getattr(self, backup.data)(backup.children)

        return {"type": "FallbackExpr", "primary": primary, "backup": backup}
            
    @v_args(inline=False)
    def img_call(self, args):
        return {"type": "ImgCall", "path": args[0].value.strip('"')}

    @v_args(inline=False)
    def program(self, args):
        includes = []
        body = []
        for arg in args:
            if isinstance(arg, dict) and arg.get("type") == "IncludeStatement":
                includes.append(arg)
            else:
                body.append(arg)
        return {"type": "Program", "includes": includes, "body": body}

    @v_args(inline=False)
    def tool_decl(self, args):
        name = str(args[0])
        body_args = args[1]
        # Handle different tool body types
        if isinstance(body_args, dict):
            if body_args.get("type") == "mcp":
                return {
                    "type": "ToolDeclaration",
                    "name": name,
                    "mcp": body_args.get("mcp")
                }
            elif body_args.get("type") == "python":
                return {
                    "type": "ToolDeclaration",
                    "name": name,
                    "python": body_args.get("python")
                }
            else:
                return {
                    "type": "ToolDeclaration",
                    "name": name,
                    "description": body_args.get("description", ""),
                    "parameters": body_args.get("parameters", {})
                }
        return {
            "type": "ToolDeclaration",
            "name": name,
            "description": body_args.get("description", ""),
            "parameters": body_args.get("parameters", {})
        }

    @v_args(inline=False)
    def tool_body(self, args):
        # Handle different tool_body types - this is a passthrough
        if args and isinstance(args[0], dict):
            return args[0]
        # Legacy format
        if len(args) >= 2:
            return {
                "description": str(args[0]).strip('"'),
                "parameters": args[1]
            }
        return {"description": "", "parameters": {}}

    @v_args(inline=False)
    def tool_body_standard(self, args):
        return {
            "description": str(args[0]).strip('"'),
            "parameters": args[1]
        }

    @v_args(inline=False)
    def tool_body_mcp(self, args):
        return {
            "type": "mcp",
            "mcp": str(args[0]).strip('"')
        }

    @v_args(inline=False)
    def tool_body_python(self, args):
        return {
            "type": "python",
            "python": str(args[0]).strip('"')
        }

    
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
        # Handle decorators (multiple @limit, @timeout, etc.)
        decorators = []
        idx = 0
        while idx < len(args):
            arg = args[idx]
            if isinstance(arg, dict) and arg.get("type") == "agent_decorator":
                decorators.append(arg)
                idx += 1
            else:
                break
        
        # Skip decorators to find name
        name = str(args[idx]) if idx < len(args) else ""
        idx += 1
        
        return_type = "str"
        if idx < len(args) and args[idx] is not None:
            if isinstance(args[idx], dict) and "value" in args[idx]:
                return_type = args[idx]["value"]
            idx += 1
        else:
            idx += 1
            
        uses = []
        if idx < len(args) and args[idx] is not None:
            uses = args[idx]
            idx += 1
        else:
            idx += 1
            
        implements = None
        if idx < len(args) and args[idx] is not None:
            implements = str(args[idx])
            idx += 1
        else:
            idx += 1
            
        properties = {}
        for arg in args[idx:]:
            if isinstance(arg, dict) and "key" in arg:
                properties[arg["key"]] = arg["value"]
        
        # Extract decorator values
        max_tokens = None
        timeout = None
        retry = None
        temperature = None
        for dec in decorators:
            dec_name = dec.get("name", "")
            dec_params = dec.get("params", {})
            if dec_name == "limit":
                max_tokens = dec_params.get("max_tokens")
            elif dec_name == "timeout":
                timeout = dec_params.get("seconds")
            elif dec_name == "retry":
                retry = dec_params.get("max_attempts")
            elif dec_name == "temperature":
                temperature = dec_params.get("value")
                
        return {
            "type": "AgentDeclaration",
            "name": name,
            "decorators": decorators,
            "max_tokens": max_tokens,
            "timeout": timeout,
            "retry": retry,
            "temperature": temperature,
            "return_type": return_type,
            "uses": uses,
            "implements": implements,
            "properties": properties,
            "prompt": properties.get("prompt", "")
        }

    @v_args(inline=False)
    def agent_decorator(self, args):
        name = str(args[0]) if args else ""
        params = {}
        for arg in args[1:]:
            if isinstance(arg, dict):
                params.update(arg)
        return {"type": "agent_decorator", "name": name, "params": params}

    @v_args(inline=False)
    def agent_decorator_name(self, args):
        return str(args[0]) if args else ""

    @v_args(inline=False)
    def agent_decorator_params(self, args):
        params = {}
        for arg in args:
            if isinstance(arg, dict):
                params.update(arg)
        return params

    @v_args(inline=False)
    def agent_decorator_param(self, args):
        key = str(args[0])
        value = args[1]
        if hasattr(value, 'value'):
            value = value.value
        try:
            value = int(value)
        except (ValueError, TypeError):
            try:
                value = float(value)
            except (ValueError, TypeError):
                pass
        return {key: value}

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

    @v_args(inline=True)
    def int_val(self, i):
        return int(i)

    @v_args(inline=True)
    def true_val(self, _):
        return True

    @v_args(inline=True)
    def false_val(self, _):
        return False

    @v_args(inline=False)
    def fallback_list_val(self, args):
        """处理 fallback_list_val 节点"""
        return args[0]  # 返回 fallback_list

    @v_args(inline=False)
    def fallback_list(self, args):
        """处理 fallback_list，返回带 fallback 标记的列表"""
        result = []
        for item in args:
            if isinstance(item, dict):
                result.append(item)
            else:
                result.append({"value": str(item).strip('"'), "is_fallback": False})
        return {"type": "fallback_list", "models": result}

    @v_args(inline=True)
    def primary_model(self, item):
        """处理主模型"""
        from lark import Token
        if isinstance(item, Token):
            value = str(item).strip('"')
            return {"value": value, "is_fallback": False}
        return {"value": str(item).strip('"'), "is_fallback": False}

    @v_args(inline=True)
    def fallback_model(self, item):
        """处理 fallback 模型"""
        from lark import Token
        if isinstance(item, Token):
            value = str(item).strip('"')
            return {"value": value, "is_fallback": True}
        return {"value": str(item).strip('"'), "is_fallback": True}

    @v_args(inline=False)
    def if_stmt(self, args):
        """if 语句"""
        condition = args[0]
        then_block = args[1]
        else_block = args[2] if len(args) > 2 else []
        return {
            "type": "IfStatement",
            "condition": condition,
            "then_block": then_block,
            "else_block": else_block
        }

    @v_args(inline=False)
    def condition(self, args):
        """条件表达式"""
        return {
            "type": "ConditionExpression",
            "left": args[0],
            "operator": str(args[1]),
            "right": args[2]
        }

    @v_args(inline=False)
    def comparison_op(self, args):
        """比较运算符"""
        return str(args[0]) if args else "=="

    @v_args(inline=False)
    def comparison_expr(self, args):
        """比较表达式"""
        return {
            "type": "ComparisonExpression",
            "left": args[0],
            "operator": str(args[1]),
            "right": args[2]
        }

    @v_args(inline=False)
    def identifier_list(self, args):
        return [str(arg) for arg in args]

    def use_identifier_list(self, args):
        return [str(arg) for arg in args]

    def use_identifier(self, args):
        return str(args[0])

    def namespaced_id(self, args):
        return f"{args[0]}.{args[1]}"

    def string_use(self, args):
        return str(args[0])[1:-1]

    def mcp_use(self, args):
        return "mcp:" + str(args[0])[1:-1]

    @v_args(inline=False)
    def flow_decl(self, args):
        # flow_decl: "flow" IDENTIFIER ["(" param_list ")"] block
        # 解析树结构: [name, params_or_None, block]
        name = str(args[0])
        params = []
        body = []
        
        # args[1] 是参数列表（可能为 None）
        # args[2] 是 block
        if len(args) > 1:
            # 检查 args[1] 是否是参数列表
            if args[1] is not None:
                if isinstance(args[1], list):
                    # 检查是否是参数定义 (有 name 和 type 键)
                    if len(args[1]) > 0 and isinstance(args[1][0], dict) and 'name' in args[1][0]:
                        params = args[1]
                    else:
                        body = args[1]
                elif isinstance(args[1], dict):
                    body = [args[1]]
        
        # args[2] 是 block（如果有参数）
        if len(args) > 2 and args[2] is not None:
            if isinstance(args[2], list):
                body = args[2]
            elif isinstance(args[2], dict):
                body = [args[2]]
        
        return {
            "type": "FlowDeclaration",
            "name": name,
            "params": params,
            "body": body
        }
    
    @v_args(inline=False)
    def param_list(self, args):
        return [arg for arg in args if arg is not None]
    
    @v_args(inline=False)
    def param(self, args):
        return {
            "name": str(args[0]),
            "type": str(args[1])
        }

    @v_args(inline=False)
    def test_decl(self, args):
        return {
            "type": "TestDeclaration",
            "name": str(args[0]).strip('"'),
            "body": args[1]
        }

    @v_args(inline=False)
    def block(self, args):
        return args

    @v_args(inline=False)
    def assignment_stmt(self, args):
        val = args[1]
        if hasattr(val, 'data') and val.data == 'fallback_expr':
            val = self.fallback_expr(val.children)
            
        return {
            "type": "AssignmentStatement",
            "target": str(args[0]),
            "value": val
        }

    @v_args(inline=False)
    def expr_stmt(self, args):
        return {
            "type": "ExpressionStatement",
            "expression": args[0]
        }

    @v_args(inline=False)
    def try_catch_stmt(self, args):
        return {
            "type": "TryCatchStatement",
            "block_try": args[0],
            "catch_err": str(args[1]),
            "block_catch": args[2]
        }

    @v_args(inline=False)
    def assert_stmt(self, args):
        return {
            "type": "AssertStatement",
            "expression": args[0]
        }

    @v_args(inline=False)
    def break_stmt(self, args):
        return {
            "type": "BreakStatement"
        }

    @v_args(inline=False)
    def semantic_if_stmt(self, args):
        condition = str(args[0]).strip('"')
        fast_match = str(args[1]).strip('"') if args[1] else None
        target = str(args[2])
        consequence = args[3]
        alternative = args[4] if len(args) > 4 and args[4] else []
        
        return {
            "type": "SemanticIfStatement",
            "condition": condition,
            "fast_match": fast_match,
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
    
    # ==================== DAG 表达式转换 ====================
    
    @v_args(inline=False)
    def dag_expr(self, args):
        """DAG表达式统一处理"""
        return args[0]  # 返回具体的dag_fork_expr, dag_merge_expr或dag_branch_expr
    
    @v_args(inline=False)
    def dag_fork_expr(self, args):
        """
        分叉表达式: expr |>> [Agent1, Agent2] 或 expr || [Agent1, Agent2]
        |>> 表示分叉后等待所有结果
        || 表示分叉后不等待（fire-and-forget）
        
        Lark 传递: args[0] = input_expr (expression)
                   args[1] = agent list (from identifier_list_as_expr)
        注意: 操作符 |>> 或 || 是 literal，不会作为单独节点传递
        默认使用 |>> (wait_all=True)
        """
        input_expr = args[0]
        
        # agents 来自 identifier_list_as_expr
        # 由于操作符是 literal token，args[1] 就是 agents 列表
        agents = args[1] if len(args) > 1 else []
        if not isinstance(agents, list):
            agents = [str(agents)]
        
        # 默认操作符为 |>> (wait_all=True)
        operator = "|>>"
        
        return {
            "type": "DAGForkExpression",
            "input": input_expr,
            "agents": agents,
            "operator": operator,
            "wait_all": True
        }
    
    @v_args(inline=False)
    def dag_merge_expr(self, args):
        """
        合流表达式: [Agent1, Agent2] &>> MergerAgent 或 [Agent1, Agent2] && MergerAgent
        &>> 表示顺序合流
        && 表示共识合流
        
        Lark 传递: args[0] = agent list (from identifier_list_as_expr)
                   args[1] = merger expression
        注意: 操作符 &>> 或 && 是 literal，不会作为单独节点传递
        """
        # agents 来自 identifier_list_as_expr
        agents = args[0] if isinstance(args[0], list) else []
        if not isinstance(agents, list):
            agents = [str(agents)]
            
        merger = args[1] if len(args) > 1 else None
        
        return {
            "type": "DAGMergeExpression",
            "agents": agents,
            "merger": merger,
            "operator": "&>>",
            "strategy": "concat"
        }
    
    @v_args(inline=False)
    def dag_branch_expr(self, args):
        """
        条件分支表达式:
        1. expr ?? TrueAgent : FalseAgent (三元形式)
        2. expr ?? { "case1" => action1 } (块形式)
        """
        input_expr = args[0]
        
        # 检查是否是块形式 (semantic_if_block 是列表)
        if len(args) == 2:
            # 块形式: args[1] 是 semantic_if_block (case 列表)
            cases = args[1]
            if isinstance(cases, list):
                return {
                    "type": "DAGBranchExpression",
                    "input": input_expr,
                    "cases": cases
                }
        
        # 三元形式
        true_agent = args[1] if len(args) > 1 else None
        false_agent = args[2] if len(args) > 2 else None
        
        return {
            "type": "DAGBranchExpression",
            "input": input_expr,
            "true_agent": true_agent,
            "false_agent": false_agent
        }
    
    @v_args(inline=False)
    def identifier_list_as_expr(self, args):
        """将方括号内的标识符列表转换为列表
        
        Lark 传递的 args 来自 identifier_list 规则
        需要将每个 Token 转换为字符串
        """
        result = []
        for arg in args:
            # identifier_list 可能包含多个 IDENTIFIER token
            if hasattr(arg, '__iter__') and not isinstance(arg, str):
                # 如果是可迭代对象但不是字符串，展开它
                for sub_arg in arg:
                    result.append(str(sub_arg))
            else:
                result.append(str(arg))
        return result

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
        args = [a for a in args if a is not None]
        arguments = []
        if len(args) > 0 and isinstance(args[-1], list):
            arguments = args.pop()
            
        if len(args) == 1:
            return {
                "type": "FunctionCallExpression",
                "function": str(args[0]),
                "arguments": arguments
            }
        elif len(args) >= 2:
            return {
                "type": "MethodCallExpression",
                "object": str(args[0]),
                "method": str(args[1]),
                "arguments": arguments
            }
        return {}

    @v_args(inline=False)
    def kwarg(self, args):
        return {
            "type": "KeywordArgument",
            "key": str(args[0]),
            "value": args[1]
        }

    @v_args(inline=False)
    def dict_access_expr(self, args):
        return {
            "type": "DictAccessExpression",
            "base": args[0],
            "key": args[1]
        }

    @v_args(inline=False)
    def property_access(self, args):
        if len(args) == 2:
            base_val = str(args[0]) if type(args[0]).__name__ == "Token" else args[0]
            return {
                "type": "PropertyAccess",
                "base": base_val,
                "property": str(args[1])
            }
        return {"type": "PropertyAccess", "base": args[0], "property": str(args[1])}

    @v_args(inline=False)
    def argument_list(self, args):
        return args

    # 新增 DAG 操作符 transformer 方法
    @v_args(inline=False)
    def dag_chain_expr(self, args):
        """链式 DAG 表达式: expr |>> [...] &>> Agent"""
        return {
            "type": "DAGChainExpression",
            "fork": args[0],
            "merge": args[1]
        }

    @v_args(inline=True)
    def string_expr(self, s):
        return {"type": "StringLiteral", "value": str(s).strip('"')}

    @v_args(inline=True)
    def id_expr(self, i):
        return {"type": "Identifier", "value": str(i)}

    @v_args(inline=False)
    def binary_expr(self, args):
        """二元表达式：字符串拼接等
        语法: binary_expr: base_expr ("+" base_expr)+
        由于 "+" 是 literal token，args 只包含 base_expr 列表
        """
        if len(args) == 1:
            return args[0]
        
        # args 是 [base_expr, base_expr, ...]，操作符固定为 "+"
        result = args[0]
        for i in range(1, len(args)):
            right = args[i]
            result = {
                "type": "BinaryExpression",
                "operator": "+",
                "left": result,
                "right": right
            }
        return result

    @v_args(inline=False)
    def std_call(self, args):
        """标准库调用: std.ns.func(...)"""
        return {
            "type": "StdCallExpression",
            "namespace": str(args[0]),
            "function": str(args[1]),
            "arguments": args[2] if len(args) > 2 else []
        }

    @v_args(inline=False)
    def semantic_if_expr(self, args):
        """semantic_if 表达式形式: semantic_if (var, "condition") { ... }"""
        return {
            "type": "SemanticIfExpression",
            "variable": str(args[0]),
            "condition": str(args[1]).strip('"'),
            "cases": args[2]
        }

    @v_args(inline=False)
    def semantic_if_block(self, args):
        """semantic_if 块: { "case1" => action1 }"""
        return args

    @v_args(inline=False)
    def semantic_if_case(self, args):
        """semantic_if case: "case" => action"""
        return {
            "pattern": str(args[0]).strip('"'),
            "action": args[1]
        }

    @v_args(inline=True)
    def string_val(self, s):
        return str(s).strip('"')

    @v_args(inline=True)
    def int_val(self, i):
        return int(i)

    @v_args(inline=True)
    def true_val(self, _):
        return True

    @v_args(inline=True)
    def false_val(self, _):
        return False

    @v_args(inline=False)
    def fallback_list_val(self, args):
        """处理 fallback_list_val 节点"""
        return args[0]

    @v_args(inline=False)
    def fallback_list(self, args):
        """处理 fallback_list，返回带 fallback 标记的列表"""
        result = []
        for item in args:
            if isinstance(item, dict):
                result.append(item)
            else:
                result.append({"value": str(item).strip('"'), "is_fallback": False})
        return {"type": "fallback_list", "models": result}

    @v_args(inline=True)
    def primary_model(self, item):
        """处理主模型"""
        from lark import Token
        if isinstance(item, Token):
            value = str(item).strip('"')
            return {"value": value, "is_fallback": False}
        return {"value": str(item).strip('"'), "is_fallback": False}

    @v_args(inline=True)
    def fallback_model(self, item):
        """处理 fallback 模型"""
        from lark import Token
        if isinstance(item, Token):
            value = str(item).strip('"')
            return {"value": value, "is_fallback": True}
        return {"value": str(item).strip('"'), "is_fallback": True}

    @v_args(inline=False)
    def if_stmt(self, args):
        """if 语句"""
        condition = args[0]
        then_block = args[1]
        else_block = args[2] if len(args) > 2 else []
        return {
            "type": "IfStatement",
            "condition": condition,
            "then_block": then_block,
            "else_block": else_block
        }

    @v_args(inline=False)
    def condition(self, args):
        """条件表达式"""
        return {
            "type": "ConditionExpression",
            "left": args[0],
            "operator": str(args[1]),
            "right": args[2]
        }

    @v_args(inline=False)
    def comparison_op(self, args):
        """比较运算符"""
        return str(args[0]) if args else "=="

    @v_args(inline=False)
    def comparison_expr(self, args):
        """比较表达式"""
        return {
            "type": "ComparisonExpression",
            "left": args[0],
            "operator": str(args[1]),
            "right": args[2]
        }

    @v_args(inline=True)
    def string_expr(self, s):
        return {"type": "StringLiteral", "value": str(s).strip('"')}

    @v_args(inline=True)
    def id_expr(self, i):
        return {"type": "Identifier", "value": str(i)}


if __name__ == "__main__":
    from nexa_parser import parse
    import os
    
    import sys
    example_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '../examples/01_hello_world.nx')
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
