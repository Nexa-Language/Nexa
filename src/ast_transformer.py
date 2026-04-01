import lark
from lark import Transformer, v_args
import json

class NexaTransformer(Transformer):
    """
    负责将 Lark 解析后生成的树结构（Tree）转化为
    Nexa 原生的轻量级 JSON / Dict 抽象语法树（AST）
    """
    
    def _ambig(self, args):
        """处理歧义树 - 优先选择内置类型分支"""
        # 对于类型歧义，优先选择内置类型 (str_type, int_type, float_type, bool_type)
        builtin_types = ['str_type', 'int_type', 'float_type', 'bool_type', 'list_type', 'dict_type']
        for child in args:
            if hasattr(child, 'data') and child.data in builtin_types:
                # 递归转换选择的子树
                return getattr(self, child.data)(child.children)
        # 默认选择第一个分支
        first = args[0]
        if hasattr(first, 'data'):
            return getattr(self, first.data)(first.children)
        return first
    
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

    
    # ===== v1.0.2: Semantic Types =====
    
    @v_args(inline=False)
    def type_decl(self, args):
        """语义类型声明 - v1.0.2"""
        name = str(args[0])
        type_def = args[1] if len(args) > 1 else None
        return {
            "type": "TypeDeclaration",
            "name": name,
            "definition": type_def
        }
    
    @v_args(inline=False)
    def constrained_type(self, args):
        """带约束的语义类型: base_type @ "constraint" """
        base_type = args[0]
        constraint = str(args[1]).strip('"') if len(args) > 1 else ""
        return {
            "type": "SemanticType",
            "base_type": base_type,
            "constraint": constraint
        }
    
    @v_args(inline=False)
    def simple_type(self, args):
        """简单类型（无约束）"""
        return args[0] if args else None
    
    @v_args(inline=False)
    def str_type(self, args):
        return {"type": "BaseType", "name": "str"}
    
    @v_args(inline=False)
    def int_type(self, args):
        return {"type": "BaseType", "name": "int"}
    
    @v_args(inline=False)
    def float_type(self, args):
        return {"type": "BaseType", "name": "float"}
    
    @v_args(inline=False)
    def bool_type(self, args):
        return {"type": "BaseType", "name": "bool"}
    
    @v_args(inline=False)
    def list_type(self, args):
        """列表类型: list[Type]"""
        element_type = args[0] if args else {"type": "BaseType", "name": "str"}
        return {
            "type": "GenericType",
            "name": "list",
            "type_params": [element_type]
        }
    
    @v_args(inline=False)
    def dict_type(self, args):
        """字典类型: dict[KeyType, ValueType]"""
        key_type = args[0] if len(args) > 0 else {"type": "BaseType", "name": "str"}
        value_type = args[1] if len(args) > 1 else {"type": "BaseType", "name": "str"}
        return {
            "type": "GenericType",
            "name": "dict",
            "type_params": [key_type, value_type]
        }
    
    @v_args(inline=True)
    def custom_type(self, name):
        """自定义类型引用 - 从 IDENTIFIER 解析"""
        return {"type": "CustomType", "name": str(name)}

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
    def multiline_string_val(self, s):
        """处理多行字符串，移除三引号并保留内部换行"""
        s = str(s)
        # 移除开头和结尾的三引号
        if s.startswith('"""') and s.endswith('"""'):
            return s[3:-3]
        return s

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
    def true_val(self):
        return True

    @v_args(inline=True)
    def false_val(self):
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
        """条件表达式 - v1.0.1-beta 使用 CMP_OP 终端"""
        from lark import Token
        op = args[1]
        if isinstance(op, Token):
            op = str(op)
        return {
            "type": "ConditionExpression",
            "left": args[0],
            "operator": op,
            "right": args[2]
        }

    @v_args(inline=False)
    def comparison_expr(self, args):
        """比较表达式 - v1.0.1-beta 使用 CMP_OP 终端"""
        if len(args) == 1:
            # 简单布尔判断 (只有表达式)
            return args[0]
        # args: [left, CMP_OP token, right]
        from lark import Token
        op = args[1]
        if isinstance(op, Token):
            op = str(op)
        return {
            "type": "ComparisonExpression",
            "left": args[0],
            "operator": op,
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
    def continue_stmt(self, args):
        """continue 语句 - v1.0.1-beta"""
        return {
            "type": "ContinueStatement"
        }

    @v_args(inline=False)
    def traditional_if_stmt(self, args):
        """传统 if/else if/else 语句 - v1.0.1-beta
        处理各种形式的 if 语句：
        1. if (...) { } - 无 else
        2. if (...) { } else { } - 只有 else
        3. if (...) { } else if (...) { } else { } - else if 链
        """
        condition = args[0]
        then_block = args[1] if len(args) > 1 else []
        
        # 收集 else if 和 else 子句
        else_if_clauses = []
        else_block = []
        
        # 处理剩余参数
        i = 2
        while i < len(args):
            arg = args[i]
            
            # 检查是否是条件（来自 else if）
            if isinstance(arg, dict) and arg.get("type") in ["ComparisonExpression", "LogicalExpression", "Identifier"]:
                # 这是一个 else if 的条件
                if i + 1 < len(args):
                    block = args[i + 1]
                    if isinstance(block, list):
                        else_if_clauses.append({
                            "type": "ElseIfClause",
                            "condition": arg,
                            "block": block
                        })
                        i += 2
                        continue
            
            # 检查是否是 block（来自 else）
            elif isinstance(arg, list):
                # 这是 else 的 block
                else_block = arg
                i += 1
                continue
            
            i += 1
        
        return {
            "type": "TraditionalIfStatement",
            "condition": condition,
            "then_block": then_block,
            "else_if_clauses": else_if_clauses,
            "else_block": else_block
        }

    @v_args(inline=False)
    def traditional_condition(self, args):
        """传统条件表达式"""
        return args[0] if args else {"type": "BooleanLiteral", "value": True}

    @v_args(inline=False)
    def logical_expr(self, args):
        """逻辑表达式 - 支持 and/or"""
        if len(args) == 1:
            return args[0]
        
        # 构建逻辑表达式链
        result = args[0]
        i = 1
        while i < len(args):
            operator = str(args[i])
            right = args[i + 1]
            result = {
                "type": "LogicalExpression",
                "left": result,
                "operator": operator,
                "right": right
            }
            i += 2
        
        return result

    @v_args(inline=False)
    def foreach_stmt(self, args):
        """for each 循环 - v1.0.1-beta"""
        if len(args) == 3:
            # for each item in iterable { block }
            return {
                "type": "ForEachStatement",
                "iterator": str(args[0]),
                "index": None,
                "iterable": args[1],
                "body": args[2]
            }
        elif len(args) == 4:
            # for each item, index in iterable { block }
            return {
                "type": "ForEachStatement",
                "iterator": str(args[0]),
                "index": str(args[1]),
                "iterable": args[2],
                "body": args[3]
            }
        return {"type": "ForEachStatement", "iterator": "", "iterable": None, "body": []}

    @v_args(inline=False)
    def while_stmt(self, args):
        """while 循环 - v1.0.1-beta"""
        return {
            "type": "WhileStatement",
            "condition": args[0] if args else {"type": "BooleanLiteral", "value": True},
            "body": args[1] if len(args) > 1 else []
        }

    @v_args(inline=False)
    def python_escape_stmt(self, args):
        """Python 逃生舱 - v1.0.1-beta
        语法: python! \"\"\"code\"\"\"
        """
        # 提取 Python 代码块 - MULTILINE_STRING
        python_code = ""
        if args:
            raw = str(args[0])
            # 移除三引号
            if raw.startswith('"""') and raw.endswith('"""'):
                python_code = raw[3:-3]
            else:
                python_code = raw
        # 移除首尾空白但保留内部换行
        python_code = python_code.strip()
        
        return {
            "type": "PythonEscapeStatement",
            "code": python_code
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
    def dag_fork_wait(self, args):
        """
        分叉表达式 (等待所有结果): expr |>> [Agent1, Agent2]
        """
        input_expr = args[0]
        agents = args[1] if len(args) > 1 else []
        if not isinstance(agents, list):
            agents = [str(agents)]
        
        return {
            "type": "DAGForkExpression",
            "input": input_expr,
            "agents": agents,
            "operator": "|>>",
            "wait_all": True
        }
    
    @v_args(inline=False)
    def dag_fork_fire_forget(self, args):
        """
        分叉表达式 (fire-and-forget): expr || [Agent1, Agent2]
        """
        input_expr = args[0]
        agents = args[1] if len(args) > 1 else []
        if not isinstance(agents, list):
            agents = [str(agents)]
        
        return {
            "type": "DAGForkExpression",
            "input": input_expr,
            "agents": agents,
            "operator": "||",
            "wait_all": False
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
    
    @v_args(inline=False)
    def dag_chain_tail(self, args):
        """处理 dag_chain_tail: (&>> | &&) base_expr
        args 可能包含: [操作符token, base_expr] 或更多元素
        返回合流 agent 的标识符
        """
        # 过滤掉操作符 token，只保留 base_expr
        # args 结构: [Token('&>>'), base_expr] 或 [Token('&&'), base_expr]
        for arg in args:
            if isinstance(arg, dict) and arg.get("type") == "Identifier":
                return arg
            elif type(arg).__name__ == "Token":
                continue
            else:
                # 可能是其他表达式类型
                return arg
        # 如果没找到，返回最后一个非 token 元素
        non_tokens = [a for a in args if type(a).__name__ != "Token"]
        return non_tokens[-1] if non_tokens else {"type": "Identifier", "value": "Unknown"}

    @v_args(inline=True)
    def string_expr(self, s):
        return {"type": "StringLiteral", "value": str(s).strip('"')}

    @v_args(inline=True)
    def id_expr(self, i):
        return {"type": "Identifier", "value": str(i)}

    @v_args(inline=False)
    def binary_expr(self, args):
        """二元表达式：支持加减乘除 - v1.0.1-beta
        语法: binary_expr: base_expr BINARY_OP base_expr
        使用 BINARY_OP 终端确保操作符正确匹配
        """
        if len(args) == 1:
            return args[0]
        
        # args 是 [left, BINARY_OP token, right]
        from lark import Token
        if len(args) == 3:
            op = args[1]
            if isinstance(op, Token):
                op = str(op)
            return {
                "type": "BinaryExpression",
                "left": args[0],
                "operator": op,
                "right": args[2]
            }
        
        # 兼容旧语法: base_expr ("+" base_expr)+
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
    def binary_op(self, args):
        """二元运算符"""
        return str(args[0]) if args else "+"

    @v_args(inline=True)
    def int_expr(self, val):
        """整数字面量"""
        return {"type": "IntLiteral", "value": int(val)}

    @v_args(inline=True)
    def float_expr(self, val):
        """浮点数字面量"""
        return {"type": "FloatLiteral", "value": float(val)}

    @v_args(inline=False)
    def true_expr(self, args):
        """布尔 true"""
        return {"type": "BooleanLiteral", "value": True}

    @v_args(inline=False)
    def false_expr(self, args):
        """布尔 false"""
        return {"type": "BooleanLiteral", "value": False}

    @v_args(inline=True)
    def multiline_string_expr(self, val):
        """多行字符串表达式"""
        s = str(val)
        if s.startswith('"""') and s.endswith('"""'):
            return {"type": "StringLiteral", "value": s[3:-3]}
        return {"type": "StringLiteral", "value": s}

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
    def true_val(self):
        return True

    @v_args(inline=True)
    def false_val(self):
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
        if len(args) == 1:
            # 简单表达式（无比较运算符）
            return args[0]
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
