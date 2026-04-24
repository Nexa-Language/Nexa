# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
# 
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# Nexa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
# ========================================================================
from src.runtime.core import nexa_fallback, nexa_img_loader
import os
import json
import pydantic
from src.runtime.stdlib import STD_NAMESPACE_MAP

BOILERPLATE = """# 此文件由 Nexa Code Generator 自动生成
import os
import json
import pydantic
from src.runtime.stdlib import STD_NAMESPACE_MAP
from src.runtime.agent import NexaAgent
from src.runtime.evaluator import nexa_semantic_eval, nexa_intent_routing
from src.runtime.orchestrator import join_agents, nexa_pipeline
from src.runtime.dag_orchestrator import dag_fanout, dag_merge, dag_branch, dag_parallel_map, SmartRouter
from src.runtime.memory import global_memory
from src.runtime.stdlib import STD_TOOLS_SCHEMA, STD_NAMESPACE_MAP
from src.runtime.secrets import nexa_secrets
from src.runtime.core import nexa_fallback, nexa_img_loader
from src.runtime.mcp_client import fetch_mcp_tools
from src.runtime.meta import runtime, get_loop_count, get_last_result, set_loop_count, set_last_result
from src.runtime.reason import reason, reason_float, reason_int, reason_bool, reason_str, reason_dict, reason_list, reason_model
from src.runtime.hitl import wait_for_human, ApprovalStatus, HITLManager
from src.runtime.contracts import ContractSpec, ContractClause, OldValues, ContractViolation, check_requires, check_ensures, capture_old_values
from src.runtime.type_system import TypeChecker, TypeInferrer, TypeViolation, TypeWarning, TypeCheckResult, TypeMode, LintMode, get_type_mode, get_lint_mode, PrimitiveTypeExpr, GenericTypeExpr, UnionTypeExpr, OptionTypeExpr, ResultTypeExpr, AliasTypeExpr, FuncTypeExpr, SemanticTypeExpr, build_type_expr_from_ast, build_protocol_fields_from_ast
# v1.2: Error Propagation (错误传播)
from src.runtime.result_types import NexaResult, NexaOption, ErrorPropagation, propagate_or_else, try_propagate, wrap_agent_result
# P3-3: Pattern Matching (模式匹配)
from src.runtime.pattern_matching import nexa_match_pattern, nexa_destructure, nexa_make_variant, _nexa_is_tuple_like, _nexa_is_list_like, _nexa_is_dict_with_keys, _nexa_is_variant, _nexa_list_rest, _nexa_dict_rest
# P3-4: ADT — Struct/Enum/Trait/Impl (代数数据类型)
from src.runtime.adt import register_struct, make_struct_instance, struct_get_field, struct_set_field, is_struct_instance, register_enum, make_variant, make_unit_variant, is_variant_instance, register_trait, register_impl, call_trait_method, lookup_struct, lookup_enum, lookup_trait, lookup_impl, ContractViolation
# P3-4: ADT — Struct/Enum/Trait/Impl (代数数据类型)
from src.runtime.adt import register_struct, make_struct_instance, struct_get_field, struct_set_field, is_struct_instance, register_enum, make_variant, make_unit_variant, is_variant_instance, register_trait, register_impl, call_trait_method, lookup_struct, lookup_enum, lookup_trait, lookup_impl, ContractViolation
# P1-3: Background Job System (后台任务系统)
from src.runtime.jobs import JobSpec, JobPriority, JobStatus, BackoffStrategy, JobRegistry, JobQueue, JobWorker, JobScheduler
# P1-4: Built-In HTTP Server (内置 HTTP 服务器)
from src.runtime.http_server import NexaHttpServer, ServerState, CorsConfig, CspConfig, NexaRequest, RouteSegment, RouteSegmentType, Route, ContractViolation, text, html, json_response, redirect, status_response, create_response, parse_form, parse_json_body, create_error_response, get_mime_type, cache_control_for, apply_security_headers, HotReloadWatcher
# P1-5: Database Integration (内置数据库集成)
from src.runtime.database import NexaDatabase, NexaSQLite, NexaPostgres, DatabaseError, query, query_one, execute, close, begin, commit, rollback, python_to_sql, sql_to_python, adapt_sql_params, agent_memory_query, agent_memory_store, agent_memory_delete, agent_memory_list, contract_violation_to_http_status, verify_wal_mode, verify_foreign_keys
# P2-1: Built-In Auth & OAuth (内置认证与 OAuth)
from src.runtime.auth import NexaAuth, ProviderConfig, AuthConfig, Session, oauth, enable_auth, get_user, get_session, jwt_sign, jwt_verify, jwt_decode, csrf_token, csrf_field, verify_csrf, require_auth, require_auth_middleware, logout_user, agent_api_key_generate, agent_api_key_verify, agent_auth_context, handle_auth_start, handle_auth_callback, handle_auth_logout
# P2-3: KV Store (内置键值存储)
from src.runtime.kv_store import NexaKVStore, KVHandle, kv_open, kv_get, kv_get_int, kv_get_str, kv_get_json, kv_set, kv_set_nx, kv_del, kv_has, kv_list, kv_incr, kv_expire, kv_ttl, kv_flush, agent_kv_query, agent_kv_store, agent_kv_context
# P2-2: Structured Concurrency (结构化并发)
from src.runtime.concurrent import NexaChannel, NexaTask, NexaSchedule, NexaConcurrencyRuntime, RUNTIME, channel, send, recv, recv_timeout, try_recv, close, select, spawn, await_task, try_await, cancel_task, parallel, race, after, schedule, cancel_schedule, sleep_ms, thread_count, parse_interval
# P2-4: Template System (模板系统)
from src.runtime.template import NexaTemplateRenderer, TemplateContentParser, _nexa_tpl_escape, _nexa_tpl_join, _nexa_tpl_safe_str, FILTER_REGISTRY, render_string, template, compile_template, render, agent_template_prompt, agent_template_slot_fill, agent_template_register, agent_template_list, agent_template_unregister

# P2-4: Template filter function aliases (for generated template code)
_nexa_tpl_filter_upper = FILTER_REGISTRY.get('upper')
_nexa_tpl_filter_uppercase = FILTER_REGISTRY.get('uppercase')
_nexa_tpl_filter_lower = FILTER_REGISTRY.get('lower')
_nexa_tpl_filter_lowercase = FILTER_REGISTRY.get('lowercase')
_nexa_tpl_filter_capitalize = FILTER_REGISTRY.get('capitalize')
_nexa_tpl_filter_trim = FILTER_REGISTRY.get('trim')
_nexa_tpl_filter_truncate = FILTER_REGISTRY.get('truncate')
_nexa_tpl_filter_replace = FILTER_REGISTRY.get('replace')
_nexa_tpl_filter_escape = FILTER_REGISTRY.get('escape')
_nexa_tpl_filter_raw = FILTER_REGISTRY.get('raw')
_nexa_tpl_filter_safe = FILTER_REGISTRY.get('safe')
_nexa_tpl_filter_default = FILTER_REGISTRY.get('default')
_nexa_tpl_filter_length = FILTER_REGISTRY.get('length')
_nexa_tpl_filter_first = FILTER_REGISTRY.get('first')
_nexa_tpl_filter_last = FILTER_REGISTRY.get('last')
_nexa_tpl_filter_reverse = FILTER_REGISTRY.get('reverse')
_nexa_tpl_filter_join = FILTER_REGISTRY.get('join')
_nexa_tpl_filter_slice = FILTER_REGISTRY.get('slice')
_nexa_tpl_filter_json = FILTER_REGISTRY.get('json')
_nexa_tpl_filter_number = FILTER_REGISTRY.get('number')
_nexa_tpl_filter_url_encode = FILTER_REGISTRY.get('url_encode')
_nexa_tpl_filter_strip_tags = FILTER_REGISTRY.get('strip_tags')
_nexa_tpl_filter_word_count = FILTER_REGISTRY.get('word_count')
_nexa_tpl_filter_line_count = FILTER_REGISTRY.get('line_count')
_nexa_tpl_filter_indent = FILTER_REGISTRY.get('indent')
_nexa_tpl_filter_date = FILTER_REGISTRY.get('date')
_nexa_tpl_filter_sort = FILTER_REGISTRY.get('sort')
_nexa_tpl_filter_unique = FILTER_REGISTRY.get('unique')
_nexa_tpl_filter_abs = FILTER_REGISTRY.get('abs')
_nexa_tpl_filter_ceil = FILTER_REGISTRY.get('ceil')
_nexa_tpl_filter_floor = FILTER_REGISTRY.get('floor')

# v1.1: 渐进式类型系统 — 初始化类型检查器
__type_checker = TypeChecker()
__type_mode = get_type_mode()

# P3-6: Null Coalescing helper (空值合并辅助函数)
def _nexa_null_coalesce(left, right):
    if left is None:
        return right
    if isinstance(left, dict) and left.get('_nexa_option_variant') == 'None':
        return right
    if isinstance(left, dict) and not left:
        return right
    return left

# P3-3: Pattern Matching (模式匹配)
from src.runtime.pattern_matching import nexa_match_pattern, nexa_destructure, nexa_make_variant, _nexa_is_tuple_like, _nexa_is_list_like, _nexa_is_dict_with_keys, _nexa_is_variant, _nexa_list_rest, _nexa_dict_rest
# P3-4: ADT — Struct/Enum/Trait/Impl (代数数据类型)
from src.runtime.adt import register_struct, make_struct_instance, struct_get_field, struct_set_field, is_struct_instance, register_enum, make_variant, make_unit_variant, is_variant_instance, register_trait, register_impl, call_trait_method, lookup_struct, lookup_enum, lookup_trait, lookup_impl, ContractViolation

# P3-5: Defer helper (延迟执行辅助函数)
def _nexa_defer_execute(stack):
    while stack:
        try:
            stack.pop()()
        except Exception:
            pass  # defer should not raise on cleanup

# P3-1: String Interpolation helper (字符串插值辅助函数)
def _nexa_interp_str(value):
    'Convert any value to string for interpolation. None -> chr(34)empty stringchr(34), dict -> JSON, etc.'
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, dict):
        if value.get('_nexa_option_variant') == 'Some':
            return _nexa_interp_str(value.get('value'))
        if value.get('_nexa_option_variant') == 'None':
            return ''
        try:
            return json.dumps(value, default=str)
        except Exception:
            return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        try:
            return json.dumps(value, default=str)
        except Exception:
            return str(value)
    return str(value)

# ==========================================
# [Target Code] 自动生成的编排逻辑
# ==========================================
"""

class CodeGenerator:
    """
    负责将 Nexa AST 转换为等价执行逻辑的 Python 代码
    """
    def __init__(self, ast):
        self.ast = ast
        self.code = [BOILERPLATE]
        self.indent_level = 0
        
        self.protocols = []
        self.tools = []
        self.agents = []
        self.flows = []
        self.tests = []
        self.types = []  # v1.0.2: Semantic Types
        self.jobs = []   # P1-3: Background Job System
        self.servers = [] # P1-4: Built-In HTTP Server
        self.db_connections = [] # P1-5: Database Integration
        self.auth_configs = [] # P2-1: Built-In Auth & OAuth
        self.require_auth_paths = [] # P2-1: require_auth 中间件路径
        self.kv_stores = [] # P2-3: KV Store
        self.concurrent_ops = [] # P2-2: Structured Concurrency
        self.structs = []        # P3-4: ADT — Struct declarations
        self.enums = []          # P3-4: ADT — Enum declarations
        self.trait_decls = []    # P3-4: ADT — Trait declarations
        self.impl_decls = []     # P3-4: ADT — Impl declarations

    def _indent(self):
        return "    " * self.indent_level
        
    def generate(self):
        for node in self.ast.get("body", []):
            if node["type"] == "ProtocolDeclaration":
                self.protocols.append(node)
            elif node["type"] == "ToolDeclaration":
                self.tools.append(node)
            elif node["type"] == "AgentDeclaration":
                self.agents.append(node)
            elif node["type"] == "FlowDeclaration":
                self.flows.append(node)
            elif node["type"] == "TestDeclaration":
                self.tests.append(node)
            elif node["type"] == "TypeDeclaration":  # v1.0.2: Semantic Types
                self.types.append(node)
            elif node["type"] == "JobDeclaration":  # P1-3: Background Job System
                self.jobs.append(node)
            elif node["type"] == "ServerDeclaration":  # P1-4: Built-In HTTP Server
                self.servers.append(node)
            elif node["type"] == "DatabaseDeclaration":  # P1-5: Database Integration
                self.db_connections.append(node)
            elif node["type"] == "AuthDeclaration":  # P2-1: Built-In Auth & OAuth
                self.auth_configs.append(node)
            elif node["type"] == "KVDeclaration":  # P2-3: KV Store
                self.kv_stores.append(node)
            elif node["type"] in ("SpawnExpression", "ParallelExpression", "RaceExpression",
                                  "ChannelDeclaration", "AfterExpression", "ScheduleExpression",
                                  "SelectExpression"):  # P2-2: Structured Concurrency
                self.concurrent_ops.append(node)
            elif node["type"] == "StructDeclaration":  # P3-4: ADT — Struct
                self.structs.append(node)
            elif node["type"] == "EnumDeclaration":    # P3-4: ADT — Enum
                self.enums.append(node)
            elif node["type"] == "TraitDeclaration":   # P3-4: ADT — Trait
                self.trait_decls.append(node)
            elif node["type"] == "ImplDeclaration":    # P3-4: ADT — Impl
                self.impl_decls.append(node)

        self._generate_adt()          # P3-4: ADT — Struct/Enum/Trait/Impl
        self._generate_types()       # v1.0.2: Semantic Types
        self._generate_auth()        # P2-1: Built-In Auth & OAuth
        self._generate_databases()   # P1-5: Database Integration
        self._generate_kv()          # P2-3: KV Store
        self._generate_concurrent()  # P2-2: Structured Concurrency
        self._generate_protocols()
        self._generate_tools()
        self._generate_agents()
        self._generate_jobs()        # P1-3: Background Job System
        self._generate_servers()     # P1-4: Built-In HTTP Server
        self._generate_flows()
        self._generate_tests()
        
        # 检测是否有 flow main 入口点
        has_flow_main = any(f["name"] == "main" for f in self.flows)
        
        self.code.append("if __name__ == \"__main__\":")
        if has_flow_main:
            self.code.append("    flow_main()")
        else:
            # 如果没有 flow main,运行所有定义的 flow
            for f in self.flows:
                flow_name = f["name"]
                self.code.append(f"    print(\"\\n=== Running flow: {flow_name} ===\")")
                self.code.append(f"    flow_{flow_name}()")
        self.code.append("")
        
        return "\n".join(self.code)

    # ===== P3-4: ADT — Struct/Enum/Trait/Impl Code Generation =====

    def _generate_adt(self):
        'P3-4: Generate ADT registration code for struct, enum, trait, and impl declarations'
        self._generate_structs()
        self._generate_enums()
        self._generate_traits()
        self._generate_impls()

    def _generate_structs(self):
        'P3-4: Generate struct registration code'
        for struct_def in self.structs:
            name = struct_def['name']
            fields = struct_def.get('fields', [])
            # Build field list using string concatenation (avoids f-string curly brace issues)
            field_strs = []
            for f in fields:
                f_name = f.get('name', '')
                f_type = f.get('field_type', None)
                if f_type:
                    field_strs.append("{'name': '" + f_name + "', 'type': '" + f_type + "'}")
                else:
                    field_strs.append("{'name': '" + f_name + "'}")
            fields_arg = '[' + ', '.join(field_strs) + ']'
            self.code.append("register_struct('" + name + "', " + fields_arg + ")")

    def _generate_enums(self):
        'P3-4: Generate enum registration code'
        for enum_def in self.enums:
            name = enum_def['name']
            variants = enum_def.get('variants', [])
            # Build variant list: [{'name': 'Some', 'fields': ['value']}, {'name': 'None', 'fields': []}]
            variant_strs = []
            for v in variants:
                v_name = v.get('name', '')
                v_fields = v.get('fields', [])
                fields_str = '[' + ', '.join("'" + f + "'" for f in v_fields) + ']'
                variant_strs.append("{'name': '" + v_name + "', 'fields': " + fields_str + "}")
            variants_arg = '[' + ', '.join(variant_strs) + ']'
            self.code.append("register_enum('" + name + "', " + variants_arg + ")")

    def _generate_traits(self):
        'P3-4: Generate trait registration code'
        for trait_def in self.trait_decls:
            name = trait_def['name']
            methods = trait_def.get('methods', [])
            # Build method list: [{'name': 'format', 'params': [], 'return_type': 'String'}]
            method_strs = []
            for m in methods:
                m_name = m.get('name', '')
                m_params = m.get('params', [])
                m_return = m.get('return_type', None)
                param_strs = []
                for p in m_params:
                    if isinstance(p, dict):
                        p_name = p.get('name', p.get('value', ''))
                        param_strs.append("'" + p_name + "'")
                    else:
                        param_strs.append("'" + str(p) + "'")
                params_arg = '[' + ', '.join(param_strs) + ']'
                return_arg = "'" + m_return + "'" if m_return else 'None'
                method_strs.append("{'name': '" + m_name + "', 'params': " + params_arg + ", 'return_type': " + return_arg + "}")
            methods_arg = '[' + ', '.join(method_strs) + ']'
            self.code.append("register_trait('" + name + "', " + methods_arg + ")")

    def _generate_impls(self):
        'P3-4: Generate impl registration code'
        for impl_def in self.impl_decls:
            trait_name = impl_def.get('trait_name', '')
            type_name = impl_def.get('type_name', '')
            methods = impl_def.get('methods', [])
            # Build method dict: {'format': lambda self: ...}
            method_entries = []
            for m in methods:
                m_name = m.get('name', '')
                m_body = m.get('body', [])
                # Generate lambda body from statements
                body_code = self._generate_impl_method_body(m_body)
                method_entries.append("'" + m_name + "': " + body_code)
            methods_arg = '{' + ', '.join(method_entries) + '}'
            self.code.append(f"register_impl('{trait_name}', '{type_name}', {methods_arg})")

    def _generate_impl_method_body(self, body_stmts):
        'P3-4: Generate Python lambda body for impl method'
        if not body_stmts:
            return 'lambda self: None'
        # For simple single-expression bodies, use lambda
        if len(body_stmts) == 1:
            stmt = body_stmts[0]
            if isinstance(stmt, dict):
                expr_str = self._resolve_expression(stmt)
                return f'lambda self: {expr_str}'
        # For multi-statement bodies, use a function definition
        lines = []
        lines.append('lambda self: (')
        for stmt in body_stmts:
            if isinstance(stmt, dict):
                stmt_str = self._generate_inline_statement(stmt)
                lines.append(f'    {stmt_str},')
        lines.append(')')
        return '\n'.join(lines)

    def _generate_types(self):
        """v1.0.2: 生成语义类型定义"""
        for type_def in self.types:
            name = type_def["name"]
            definition = type_def.get("definition", {})
            
            # 根据类型定义生成 Pydantic 类型
            type_type = definition.get("type", "BaseType")
            
            if type_type == "SemanticType":
                # 带语义约束的类型
                base_type = definition.get("base_type", {})
                base_name = base_type.get("name", "str")
                constraint = definition.get("constraint", "")
                
                # 生成带验证器的 Pydantic 类型
                self.code.append(f'class {name}(pydantic.BaseModel):')
                self.code.append(f'    value: {base_name}')
                self.code.append('')
                self.code.append(f'    @pydantic.field_validator("value")')
                self.code.append(f'    def validate_semantic(cls, v):')
                self.code.append(f'        """语义约束: {constraint}"""')
                self.code.append(f'        # TODO: 使用 LLM 进行语义验证')
                self.code.append(f'        return v')
                self.code.append('')
                
            elif type_type == "BaseType":
                # 简单类型别名
                base_name = definition.get("name", "str")
                self.code.append(f'{name} = {base_name}')
                self.code.append('')
                
            elif type_type == "GenericType":
                # 泛型类型 (list, dict)
                gen_name = definition.get("name", "list")
                type_params = definition.get("type_params", [])
                
                if gen_name == "list":
                    elem_type = self._resolve_type_name(type_params[0] if type_params else {"name": "str"})
                    self.code.append(f'{name} = list[{elem_type}]')
                    self.code.append('')
                elif gen_name == "dict":
                    key_type = self._resolve_type_name(type_params[0] if type_params else {"name": "str"})
                    val_type = self._resolve_type_name(type_params[1] if len(type_params) > 1 else {"name": "str"})
                    self.code.append(f'{name} = dict[{key_type}, {val_type}]')
                    self.code.append('')
                    
            elif type_type == "CustomType":
                # 自定义类型引用
                custom_name = definition.get("name", "str")
                self.code.append(f'{name} = {custom_name}')
                self.code.append('')
    
    def _resolve_type_name(self, type_def):
        """将类型定义转换为 Python 类型名"""
        if isinstance(type_def, dict):
            t_type = type_def.get("type", "BaseType")
            if t_type == "BaseType":
                return type_def.get("name", "str")
            elif t_type == "CustomType":
                return type_def.get("name", "str")
            elif t_type == "GenericType":
                return "list"  # 简化处理
        return "str"
    
    # ===== v1.1: 渐进式类型系统辅助方法 =====
    
    def _type_expr_to_python_type(self, type_expr: dict) -> str:
        """将 AST 类型表达式转换为 Python 类型字符串 (用于 Pydantic 模型字段)
        
        Args:
            type_expr: AST 类型表达式字典
        
        Returns:
            Python 类型字符串,如 "str", "int", "list[str]", "Optional[float]"
        """
        if not isinstance(type_expr, dict):
            # 简单字符串类型名
            if type_expr in ("str", "int", "float", "bool"):
                return type_expr
            return "Any"
        
        node_type = type_expr.get("type", "")
        
        if node_type == "BaseType":
            name = type_expr.get("name", "str")
            if name == "unit":
                return "None"
            return name
        
        elif node_type == "GenericType":
            name = type_expr.get("name", "list")
            type_params = type_expr.get("type_params", [])
            params_str = ", ".join([self._type_expr_to_python_type(p) for p in type_params])
            if name == "list":
                elem = self._type_expr_to_python_type(type_params[0]) if type_params else "Any"
                return f"list[{elem}]"
            elif name == "dict":
                key = self._type_expr_to_python_type(type_params[0]) if type_params else "str"
                val = self._type_expr_to_python_type(type_params[1]) if len(type_params) > 1 else "Any"
                return f"dict[{key}, {val}]"
            return f"{name}[{params_str}]"
        
        elif node_type == "CustomType":
            return type_expr.get("name", "Any")
        
        elif node_type == "OptionTypeExpr":
            inner = self._type_expr_to_python_type(type_expr.get("inner", {}))
            return f"Optional[{inner}]"
        
        elif node_type == "ResultTypeExpr":
            ok = self._type_expr_to_python_type(type_expr.get("ok_type", {}))
            err = self._type_expr_to_python_type(type_expr.get("err_type", {}))
            return f"Union[{ok}, {err}]"
        
        elif node_type == "UnionTypeExpr":
            types = [self._type_expr_to_python_type(t) for t in type_expr.get("types", [])]
            return f"Union[{', '.join(types)}]"
        
        elif node_type == "SemanticType":
            return self._type_expr_to_python_type(type_expr.get("base_type", {}))
        
        return "Any"
    
    def _type_expr_to_constructor(self, type_expr: dict) -> str:
        """将 AST 类型表达式转换为 TypeExpr 构造器代码字符串 (用于运行时类型注册)
        
        Args:
            type_expr: AST 类型表达式字典
        
        Returns:
            Python 构造器代码字符串,如 'PrimitiveTypeExpr("str")', 'GenericTypeExpr("list", [PrimitiveTypeExpr("int")])'
        """
        if not isinstance(type_expr, dict):
            if type_expr in ("str", "int", "float", "bool", "unit"):
                return f'PrimitiveTypeExpr("{type_expr}")'
            return f'AliasTypeExpr("{type_expr}")'
        
        node_type = type_expr.get("type", "")
        
        if node_type == "BaseType":
            name = type_expr.get("name", "str")
            return f'PrimitiveTypeExpr("{name}")'
        
        elif node_type == "GenericType":
            name = type_expr.get("name", "list")
            type_params = type_expr.get("type_params", [])
            params_code = ", ".join([self._type_expr_to_constructor(p) for p in type_params])
            if name == "Option":
                inner_code = self._type_expr_to_constructor(type_params[0]) if type_params else 'AliasTypeExpr("Any")'
                return f'OptionTypeExpr({inner_code})'
            elif name == "Result":
                ok_code = self._type_expr_to_constructor(type_params[0]) if type_params else 'AliasTypeExpr("Any")'
                err_code = self._type_expr_to_constructor(type_params[1]) if len(type_params) > 1 else 'AliasTypeExpr("Any")'
                return f'ResultTypeExpr({ok_code}, {err_code})'
            return f'GenericTypeExpr("{name}", [{params_code}])'
        
        elif node_type == "CustomType":
            name = type_expr.get("name", "")
            return f'AliasTypeExpr("{name}")'
        
        elif node_type == "OptionTypeExpr":
            inner_code = self._type_expr_to_constructor(type_expr.get("inner", {}))
            return f'OptionTypeExpr({inner_code})'
        
        elif node_type == "ResultTypeExpr":
            ok_code = self._type_expr_to_constructor(type_expr.get("ok_type", {}))
            err_code = self._type_expr_to_constructor(type_expr.get("err_type", {}))
            return f'ResultTypeExpr({ok_code}, {err_code})'
        
        elif node_type == "UnionTypeExpr":
            types_code = ", ".join([self._type_expr_to_constructor(t) for t in type_expr.get("types", [])])
            return f'UnionTypeExpr([{types_code}])'
        
        elif node_type == "SemanticType":
            base_code = self._type_expr_to_constructor(type_expr.get("base_type", {}))
            constraint = type_expr.get("constraint", "")
            escaped_constraint = constraint.replace("\\", "\\\\").replace('"', '\\"')
            return f'SemanticTypeExpr({base_code}, "{escaped_constraint}")'
        
        return 'AliasTypeExpr("Any")'

    def _generate_auth(self):
        '''P2-1: 生成 Auth 配置代码

        将 AuthDeclaration AST 节点转换为 Python 代码:
        - enable_auth([oauth("google", ...)], map { "session_secret": ... })
        - 为 server 添加 require_auth 中间件
        '''
        if not self.auth_configs:
            return

        self.code.append('# P2-1: Auth Configuration (认证配置)')
        self.code.append('')

        for auth_node in self.auth_configs:
            name = auth_node.get('name', 'auth_config')
            providers = auth_node.get('providers', [])
            options = auth_node.get('options', {})

            # 生成 provider 列表代码
            provider_codes = []
            for p in providers:
                p_name = p.get('name', '')
                p_client_id = p.get('client_id', '')
                p_client_secret = p.get('client_secret', '')
                provider_codes.append(f'oauth("{p_name}", "{p_client_id}", "{p_client_secret}")')

            providers_str = ', '.join(provider_codes)

            # 生成 options
            options_parts = []
            for k, v in options.items():
                options_parts.append(f'"{k}": {json.dumps(v, ensure_ascii=False)}')
            if options_parts:
                options_str = f', map {{{", ".join(options_parts)}}}'
            else:
                options_str = ''

            self.code.append(f'{name} = enable_auth([{providers_str}]{options_str})')
            self.code.append('')

        # 生成 require_auth 中间件 (如果有)
        if self.require_auth_paths:
            self.code.append('# P2-1: require_auth 中间件')
            self.code.append('def __require_auth_middleware(req):')
            self.code.append('    result = require_auth(req)')
            self.code.append('    if result is not None:')
            self.code.append('        return result  # Auth failed, return error response')
            self.code.append('    return req  # Auth passed, continue request')
            self.code.append('')

        self.code.append('')

    def _generate_databases(self):
        """P1-5: 生成数据库连接代码
        
        将 DatabaseDeclaration AST 节点转换为 Python 代码:
        - 根据连接字符串检测数据库类型 (sqlite vs postgres)
        - 创建连接句柄变量
        - 生成 Agent 记忆绑定代码 (如有 agent 使用 memory = db)
        - 生成错误处理代码
        """
        if not self.db_connections:
            return
        
        self.code.append("# P1-5: Database Connections (数据库连接)")
        self.code.append("")
        
        for db_node in self.db_connections:
            name = db_node.get("name", "db")
            conn_str = db_node.get("connection_string", ":memory:")
            
            # 检测数据库类型
            if conn_str.startswith("postgres://") or conn_str.startswith("postgresql://"):
                db_type = "postgres"
                connect_code = f"NexaPostgres.connect('{conn_str}')"
            else:
                db_type = "sqlite"
                # 处理 sqlite:// 前缀
                if conn_str.startswith("sqlite://"):
                    connect_code = f"NexaSQLite.connect('{conn_str}')"
                else:
                    connect_code = f"NexaSQLite.connect('{conn_str}')"
            
            # 生成连接创建代码 (带错误处理)
            self.code.append(f"# Database connection: {name}")
            self.code.append("try:")
            self.code.append(f"    {name} = {connect_code}")
            self.code.append(f"    print(f'Database {name} connected ({db_type})')")
            self.code.append("except ContractViolation as e:")
            self.code.append(f"    print(f'Database {name} connection failed: {{e}}')")
            self.code.append(f"    {name} = None")
            self.code.append("")
        
        # 生成 Agent 记忆绑定代码
        for agent_node in self.agents:
            agent_name = agent_node.get("name", "")
            agent_props = agent_node.get("properties", {})
            
            # 检查 agent 是否使用 memory = db(...)
            for prop in agent_props:
                if isinstance(prop, dict):
                    prop_key = prop.get("key", "")
                    prop_val = prop.get("value", "")
                    
                    # 检测 memory = db(db_name) 模式
                    if prop_key == "memory" and isinstance(prop_val, str) and prop_val.startswith("db("):
                        # 提取数据库连接名
                        db_name = prop_val.replace("db(", "").replace(")", "").strip()
                        self.code.append(f"# Agent {agent_name} memory binding to {db_name}")
                        self.code.append(f"def _memory_store_{agent_name}(key, value):")
                        self.code.append(f"    if {db_name} is not None:")
                        self.code.append(f"        return agent_memory_store({db_name}, '{agent_name}', key, value)")
                        self.code.append(f"    return False")
                        self.code.append("")
                        self.code.append(f"def _memory_query_{agent_name}(key):")
                        self.code.append(f"    if {db_name} is not None:")
                        self.code.append(f"        return agent_memory_query({db_name}, '{agent_name}', key)")
                        self.code.append(f"    return None")
                        self.code.append("")
        
        self.code.append("")

    def _generate_kv(self):
        '''P2-3: 生成 KV Store 配置代码

        将 KVDeclaration AST 节点转换为 Python 代码:
        - kv_open(path) 创建 KV 存储句柄
        - 为 Agent 生成 KV 上下文注入代码（如有）
        '''
        if not self.kv_stores:
            return

        self.code.append("# P2-3: KV Store Configuration (键值存储配置)")
        self.code.append("")

        for kv_node in self.kv_stores:
            name = kv_node.get("name", "kv_store")
            path = kv_node.get("path", ":memory:")

            self.code.append(f"# KV store: {name}")
            self.code.append("try:")
            self.code.append(f"    {name} = kv_open('{path}')")
            self.code.append(f"    print(f'KV store {name} opened (sqlite, path={path})')")
            self.code.append("except ContractViolation as e:")
            self.code.append(f"    print(f'KV store {name} open failed: {{e}}')")
            self.code.append(f"    {name} = None")
            self.code.append("")

        self.code.append("")

    def _generate_concurrent(self):
        '''P2-2: 生成结构化并发代码

        将并发相关 AST 节点转换为 Python 代码:
        - SpawnExpression → spawn(handler)
        - ParallelExpression → parallel([handlers])
        - RaceExpression → race([handlers])
        - ChannelDeclaration → channel()
        - AfterExpression → after(delay, handler)
        - ScheduleExpression → schedule(interval, handler)
        - SelectExpression → select(channels, timeout?)
        '''
        if not self.concurrent_ops:
            return

        self.code.append("# P2-2: Structured Concurrency (结构化并发)")
        self.code.append("")

        for op in self.concurrent_ops:
            op_type = op.get("type")
            if op_type == "SpawnExpression":
                handler_str = self._resolve_expression(op.get("handler", {"type": "Identifier", "value": "None"}))
                self.code.append(f"spawn({handler_str})")
            elif op_type == "ParallelExpression":
                handlers_str = self._resolve_expression(op.get("handlers", {"type": "Identifier", "value": "[]"}))
                self.code.append(f"parallel({handlers_str})")
            elif op_type == "RaceExpression":
                handlers_str = self._resolve_expression(op.get("handlers", {"type": "Identifier", "value": "[]"}))
                self.code.append(f"race({handlers_str})")
            elif op_type == "ChannelDeclaration":
                self.code.append("channel()")
            elif op_type == "AfterExpression":
                delay_str = self._resolve_expression(op.get("delay", {"type": "Identifier", "value": "0"}))
                handler_str = self._resolve_expression(op.get("handler", {"type": "Identifier", "value": "None"}))
                self.code.append(f"after({delay_str}, {handler_str})")
            elif op_type == "ScheduleExpression":
                interval_str = self._resolve_expression(op.get("interval", {"type": "Identifier", "value": "0"}))
                handler_str = self._resolve_expression(op.get("handler", {"type": "Identifier", "value": "None"}))
                self.code.append(f"schedule({interval_str}, {handler_str})")
            elif op_type == "SelectExpression":
                channels_str = self._resolve_expression(op.get("channels", {"type": "Identifier", "value": "[]"}))
                timeout_str = ""
                if op.get("timeout"):
                    timeout_str = f", {self._resolve_expression(op['timeout'])}"
                self.code.append(f"select({channels_str}{timeout_str})")

        self.code.append("")

    def _generate_protocols(self):
        for proto in self.protocols:
            name = proto["name"]
            self.code.append(f'class {name}(pydantic.BaseModel):')
            
            # v1.1: 使用 field_types 中的完整类型表达式生成 Pydantic 模型
            field_types = proto.get("field_types", {})
            
            for f_name, f_type in proto["fields"].items():
                # 优先使用类型表达式信息
                if f_name in field_types:
                    py_type = self._type_expr_to_python_type(field_types[f_name])
                else:
                    # 旧格式兼容:从字符串推断 Python 类型
                    py_type = "str"
                    if f_type == "int": py_type = "int"
                    if f_type == "float": py_type = "float"
                    if f_type == "bool": py_type = "bool"
                    if f_type.startswith("list"): py_type = "list"
                    if f_type.startswith("dict"): py_type = "dict"
                self.code.append(f'    {f_name}: {py_type}')
            self.code.append('')
            
            # v1.1: 注册 Protocol 到类型检查器
            self.code.append(f'# Type: Register protocol "{name}" fields in type checker')
            for f_name, f_type in proto["fields"].items():
                if f_name in field_types:
                    type_expr_code = self._type_expr_to_constructor(field_types[f_name])
                    self.code.append(f'__type_checker.register_protocol_field("{name}", "{f_name}", {type_expr_code})')
                else:
                    simple_type_map = {"str": 'PrimitiveTypeExpr("str")', "int": 'PrimitiveTypeExpr("int")',
                                       "float": 'PrimitiveTypeExpr("float")', "bool": 'PrimitiveTypeExpr("bool")'}
                    type_expr_code = simple_type_map.get(f_type, 'AliasTypeExpr("Any")')
                    self.code.append(f'__type_checker.register_protocol_field("{name}", "{f_name}", {type_expr_code})')
            self.code.append('')

    def _generate_tools(self):
        for tool in self.tools:
            name = tool["name"]
            
            # Handle MCP tools
            if "mcp" in tool:
                tool_code = f"""__tool_{name}_schema = {{
    "name": "{name}",
    "mcp": "{tool['mcp']}"
}}
"""
                self.code.append(tool_code)
                continue
            
            # Handle Python tools
            if "python" in tool:
                tool_code = f"""__tool_{name}_schema = {{
    "name": "{name}",
    "python": "{tool['python']}"
}}
"""
                self.code.append(tool_code)
                continue
            
            # Handle standard tools
            desc = tool.get("description", "")
            parameters = tool.get("parameters", {})
            if parameters:
                props = ",\n        ".join([f'"{k}": {{"type": "{v}"}}' for k, v in parameters.items()])
                reqs = ", ".join([f'"{k}"' for k in parameters.keys()])
            else:
                props = ""
                reqs = ""
            
            tool_code = f"""__tool_{name}_schema = {{
    "name": "{name}",
    "description": "{desc}",
    "parameters": {{
        "type": "object",
        "properties": {{
            {props}
        }},
        "required": [{reqs}]
    }}
}}
"""
            self.code.append(tool_code)

    def _generate_agents(self):
        for agent in self.agents:
            name = agent["name"]
            prompt = agent.get("prompt", "")
            uses = agent.get("uses", [])
            properties = agent.get("properties", {})
            model_raw = properties.get("model", '"minimax-m2.5"')
            if isinstance(model_raw, dict) and model_raw.get("type") == "fallback_list":
                # Handle fallback list - use primary model
                models = model_raw.get("models", [])
                primary_models = [m["value"] for m in models if not m.get("is_fallback", False)]
                fallback_models = [m["value"] for m in models if m.get("is_fallback", False)]
                model = primary_models[0] if primary_models else "minimax-m2.5"
                fallback_model = fallback_models[0] if fallback_models else None
            elif isinstance(model_raw, str):
                model = model_raw.strip('"')
                fallback_model = None
            else:
                model = "minimax-m2.5"
                fallback_model = None
            role_raw = properties.get("role", "")
            role = role_raw  # 保留原始值,不 strip
            memory_scope = properties.get("memory", '"local"').strip('"')
            stream_val = properties.get("stream", '"false"').strip('"').lower()
            stream = "True" if stream_val == "true" else "False"
            cache_val = properties.get("cache", '"false"').strip('"').lower()
            cache = "True" if cache_val == "true" else "False"
            max_history_turns = properties.get("max_history_turns", 'None').strip('"')
            experience = properties.get("experience", '""').strip('"')
            # 新增: timeout 和 retry 属性
            timeout = properties.get("timeout", "30")
            retry = properties.get("retry", "3")

            
            tool_refs_list = []
            for t in uses:
                if t == "secrets.nxs":
                    continue
                if t.endswith(".md"):
                    # Parse dynamic skills from markdown
                    md_path = os.path.join(os.path.dirname(self.source_path) if hasattr(self, 'source_path') else ".", t)
                    try:
                        with open(md_path, "r", encoding="utf-8") as mdf:
                            md_content = mdf.read()
                        import re
                        # simple parser: find ## Tool: <name> and the JSON blocks below it
                        blocks = re.split(r'## Tool:\s*([A-Za-z0-9_]+)', md_content)
                        for i in range(1, len(blocks), 2):
                            tool_name = blocks[i]
                            tool_body = blocks[i+1]
                            # Try to extract JSON block
                            json_match = re.search(r'```json\s*(.*?)\s*```', tool_body, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(1)
                                try:
                                    import json
                                    schema_dict = json.loads(json_str)
                                    desc = schema_dict.pop("description", f"Dynamic tool {tool_name}")
                                    final_schema = {
                                        "name": tool_name,
                                        "description": desc,
                                        "parameters": schema_dict
                                    }
                                    code_str = f"__tool_{tool_name}_schema = {json.dumps(final_schema, indent=4, ensure_ascii=False)}"
                                    self.code.append(code_str)
                                    tool_refs_list.append(f"__tool_{tool_name}_schema")
                                except Exception as parse_e:
                                    print(f"⚠️ Warning: Failed to parse JSON for tool {tool_name}: {parse_e}")
                    except Exception as e:
                        print(f"⚠️ Warning: Failed to load {t}: {e}")
                elif t.startswith("mcp:"):
                    uri = t[4:]
                    tool_refs_list.append(f"*fetch_mcp_tools('{uri}')")
                elif t.startswith("std."):
                    if t in STD_NAMESPACE_MAP:
                        for fn_name in STD_NAMESPACE_MAP[t]:
                            tool_refs_list.append(f"STD_TOOLS_SCHEMA['{fn_name}']")
                    else:
                        print(f"⚠️ Warning: Unknown standard namespace '{t}'")
                else:
                    tool_refs_list.append(f"__tool_{t}_schema")
            tool_refs = ", ".join(tool_refs_list)
            implements = agent.get("implements")
            max_tokens = agent.get("max_tokens")
            
            # IDD: 输出 @implements/@supports 注解为注释(保留 intent 链接)
            annotations = self.ast.get("annotations", [])
            for ann in annotations:
                if ann.get("agent_name") == name:
                    if ann.get("annotation_type") == "implements":
                        self.code.append(f'# @implements: {ann["feature_id"]}')
                    elif ann.get("annotation_type") == "supports":
                        self.code.append(f'# @supports: {ann["constraint_id"]}')
            
            # Design by Contract: 生成契约规格
            requires_clauses = agent.get("requires", [])
            ensures_clauses = agent.get("ensures", [])
            contract_code = self._generate_contract_spec(name, requires_clauses, ensures_clauses)
            
            self.code.append(f'{name} = NexaAgent(')
            self.code.append(f'    name="{name}",')
            # 处理多行 prompt,使用三引号
            if '\n' in prompt:
                self.code.append(f'    prompt="""{prompt}""",')
            else:
                self.code.append(f'    prompt="{prompt}",')
            self.code.append(f'    model="{model}",')
            # 处理多行 role,使用三引号
            if '\n' in role:
                self.code.append(f'    role="""{role}""",')
            else:
                self.code.append(f'    role="{role}",')
            self.code.append(f'    memory_scope="{memory_scope}",')
            self.code.append(f'    stream={stream},')
            self.code.append(f'    cache={cache},')
            if max_history_turns != "None":
                self.code.append(f'    max_history_turns={max_history_turns},')
            if experience:
                self.code.append(f'    experience="{experience}",')

            if implements:
                self.code.append(f'    protocol={implements},')
            if max_tokens:
                self.code.append(f'    max_tokens={max_tokens},')
            # 新增: timeout 和 retry 参数
            self.code.append(f'    timeout={timeout},')
            self.code.append(f'    retry={retry},')
            # Design by Contract: 将契约规格传递给 NexaAgent
            if contract_code:
                self.code.append(f'    contracts={contract_code},')
            self.code.append(f'    tools=[{tool_refs}]')
            self.code.append(f')\n')
            
    def _generate_jobs(self):
        """P1-3: 生成后台任务系统代码
        
        每个 Job 声明生成:
        1. perform 函数定义
        2. on_failure 函数定义(如果有)
        3. JobSpec 注册代码
        4. JobQueue.enqueue 辅助函数
        """
        if not self.jobs:
            return
        
        self.code.append("\n# ===== P1-3: Background Job System (后台任务系统) =====")
        self.code.append("# 配置 JobQueue 后端(默认内存后端,零配置)")
        self.code.append("JobQueue.configure(backend='memory')")
        self.code.append("")
        
        for job in self.jobs:
            name = job["name"]
            queue = job["queue"]
            config = job.get("config", {})
            options = job.get("options", {})
            perform = job.get("perform")
            on_failure = job.get("on_failure")
            
            # 合并 options 到 config
            merged_config = {**options, **config}
            
            # 1. 生成 perform 函数
            perform_params = []
            if perform:
                perform_params = perform.get("params", [])
            
            param_str = ", ".join(perform_params)
            self.code.append(f"# Job: {name} on {queue}")
            self.code.append(f"def _job_{name}_perform(args):")
            self.code.append(f"    # Job {name} perform function")
            
            # 将 args 字典中的值解构到局部变量
            if perform_params:
                self.code.append(f"    # 解构参数")
                for p in perform_params:
                    self.code.append(f"    {p} = args.get('{p}', None)")
            
            # 生成 perform 体
            if perform and perform.get("body"):
                body_stmts = perform.get("body", [])
                if isinstance(body_stmts, list):
                    for stmt in body_stmts:
                        if isinstance(stmt, dict):
                            stmt_code = self._generate_flow_stmt_code(stmt, indent=1)
                            if stmt_code:
                                self.code.append(f"    {stmt_code}")
                elif isinstance(body_stmts, str):
                    self.code.append(f"    {body_stmts}")
            else:
                # 如果没有 perform 体,生成占位代码
                self.code.append(f"    # TODO: 实现 {name} 的执行逻辑")
                self.code.append(f"    pass")
            
            self.code.append("")
            
            # 2. 生成 on_failure 函数(如果有)
            if on_failure:
                error_param = on_failure.get("error_param", "error")
                attempt_param = on_failure.get("attempt_param", "attempt")
                self.code.append(f"def _job_{name}_on_failure({error_param}, {attempt_param}):")
                self.code.append(f"    # Job {name} on_failure callback")
                
                on_failure_body = on_failure.get("body", [])
                if isinstance(on_failure_body, list):
                    for stmt in on_failure_body:
                        if isinstance(stmt, dict):
                            stmt_code = self._generate_flow_stmt_code(stmt, indent=1)
                            if stmt_code:
                                self.code.append(f"    {stmt_code}")
                elif isinstance(on_failure_body, str):
                    self.code.append(f"    {on_failure_body}")
                else:
                    self.code.append(f"    print(f\"Job {name} failed: {{error}}, attempt {{attempt}}\")")
                
                self.code.append("")
            
            # 3. 生成 JobSpec 注册代码
            priority = merged_config.get("priority", "normal")
            retry_count = merged_config.get("retry", 3)
            timeout = merged_config.get("timeout", 30)
            unique_spec = merged_config.get("unique", None)
            backoff = merged_config.get("backoff", "exponential")
            
            # 处理 timeout 中的单位(120s -> 120)
            if isinstance(timeout, str):
                timeout = timeout.rstrip('s').rstrip('S')
                try:
                    timeout = float(timeout)
                except ValueError:
                    timeout = 30.0
            
            # 处理 unique 规格("args for 1h" -> unique_spec="args for 1h", unique_duration=3600)
            unique_duration = 3600.0
            if unique_spec and isinstance(unique_spec, str):
                # 尝试解析 "args for Xh/Xm/Xs" 格式
                import re as _re
                duration_match = _re.search(r'for\s+(\d+)(h|m|s)', unique_spec)
                if duration_match:
                    val = int(duration_match.group(1))
                    unit = duration_match.group(2)
                    if unit == 'h':
                        unique_duration = val * 3600
                    elif unit == 'm':
                        unique_duration = val * 60
                    elif unit == 's':
                        unique_duration = val
            
            # 检查是否是 Agent Job
            is_agent_job = False
            agent_name = None
            if perform and perform.get("body"):
                # 检查 perform 体是否包含 Agent.run() 调用
                body_stmts = perform.get("body", [])
                if isinstance(body_stmts, list):
                    for stmt in body_stmts:
                        if isinstance(stmt, dict):
                            # 检查是否有 method_call 类型的表达式
                            expr_type = stmt.get("type", "")
                            if "method_call" in str(stmt):
                                # 尝试从表达式中提取 Agent 名称
                                agent_name = stmt.get("agent", stmt.get("object", None))
                                if agent_name:
                                    is_agent_job = True
                                    break
            
            on_failure_ref = f"_job_{name}_on_failure" if on_failure else "None"
            
            self.code.append(f"# 注册 JobSpec")
            self.code.append(f"JobRegistry.register(JobSpec(")
            self.code.append(f"    name='{name}',")
            self.code.append(f"    queue='{queue}',")
            self.code.append(f"    priority=JobPriority.{priority.upper()},")
            self.code.append(f"    retry_count={retry_count},")
            self.code.append(f"    timeout={timeout},")
            if unique_spec:
                self.code.append(f"    unique_spec='{unique_spec}',")
                self.code.append(f"    unique_duration={unique_duration},")
            self.code.append(f"    backoff_strategy=BackoffStrategy.{backoff.upper()},")
            self.code.append(f"    perform_fn=_job_{name}_perform,")
            if on_failure:
                self.code.append(f"    on_failure_fn=_job_{name}_on_failure,")
            else:
                self.code.append(f"    on_failure_fn=None,")
            if is_agent_job and agent_name:
                self.code.append(f"    is_agent_job=True,")
                self.code.append(f"    agent_name='{agent_name}',")
            self.code.append(f"))")
            self.code.append("")
            
            # 4. 生成入队辅助函数
            self.code.append(f"# {name} 入队辅助函数")
            self.code.append(f"def {name}_enqueue(args, options=None):")
            self.code.append(f"    # Enqueue {name} job")
            self.code.append(f"    return JobQueue.enqueue('{name}', args, options=options)")
            self.code.append("")
            self.code.append(f"def {name}_enqueue_in(delay_seconds, args, options=None):")
            self.code.append(f"    # Delayed enqueue {name} job")
            self.code.append(f"    return JobQueue.enqueue_in('{name}', delay_seconds, args, options=options)")
            self.code.append("")
            self.code.append(f"def {name}_enqueue_at(specific_time, args, options=None):")
            self.code.append(f"    # Scheduled enqueue {name} job")
            self.code.append(f"    return JobQueue.enqueue_at('{name}', specific_time, args, options=options)")
            self.code.append("")
    
    def _generate_servers(self):
        """P1-4: 生成内置 HTTP 服务器代码
        
        将 ServerDeclaration AST 节点转换为 Python 代码:
        - 创建 NexaHttpServer 实例
        - 注册路由（fn/agent/dag/semantic handler）
        - 配置 CORS/CSP/中间件
        - 配置静态文件目录
        - 生成 handler_map 和 agent_map
        - 启动 server.serve(port)
        """
        for server_node in self.servers:
            port = server_node.get("port", 8080)
            directives = server_node.get("directives", [])
            routes = server_node.get("routes", [])
            groups = server_node.get("groups", [])
            
            # Create server instance
            server_var = f"__http_server_{port}"
            self.code.append(f"# P1-4: HTTP Server on port {port}")
            self.code.append(f"{server_var} = NexaHttpServer(port={port})")
            self.code.append("")
            
            # Process directives
            for directive in directives:
                d_type = directive.get("type", "")
                if d_type == "ServerStatic":
                    url_prefix = directive.get("url_prefix", "/static")
                    fs_path = directive.get("filesystem_path", "./public")
                    self.code.append(f"{server_var}.static('{url_prefix}', '{fs_path}')")
                elif d_type == "ServerCors":
                    config = directive.get("config", {})
                    config_str = json.dumps(config, ensure_ascii=False)
                    self.code.append(f"{server_var}.cors({config_str})")
                elif d_type == "ServerMiddleware":
                    mw_names = directive.get("middleware_names", [])
                    for mw_name in mw_names:
                        self.code.append(f"{server_var}.use_middleware({mw_name})")
                elif d_type == "RequireAuth":
                    # P2-1: require_auth 中间件
                    auth_path = directive.get("path", "/")
                    self.require_auth_paths.append(auth_path)
                    self.code.append(f"{server_var}.use_middleware(require_auth_middleware)")
                    self.code.append(f"# Protected path: {auth_path}")
            
            # Process routes
            for route_node in routes:
                method = route_node.get("method", "GET")
                pattern = route_node.get("pattern", "/")
                handler = route_node.get("handler", "")
                handler_type = route_node.get("handler_type", "fn")
                dag_chain = route_node.get("dag_chain", [])
                
                if handler_type == "semantic":
                    self.code.append(f"{server_var}.semantic_route('{pattern}', '{handler}')")
                elif handler_type == "dag":
                    dag_str = json.dumps(dag_chain, ensure_ascii=False)
                    self.code.append(f"{server_var}.route('{method}', '{pattern}', '{handler}', handler_type='dag', dag_chain={dag_str})")
                elif handler_type == "agent":
                    self.code.append(f"{server_var}.route('{method}', '{pattern}', '{handler}', handler_type='agent')")
                else:  # fn
                    self.code.append(f"{server_var}.route('{method}', '{pattern}', '{handler}')")
            
            # Process groups
            for group in groups:
                prefix = group.get("prefix", "")
                group_routes = group.get("routes", [])
                group_directives = group.get("directives", [])
                
                for directive in group_directives:
                    d_type = directive.get("type", "")
                    if d_type == "ServerMiddleware":
                        mw_names = directive.get("middleware_names", [])
                        for mw_name in mw_names:
                            self.code.append(f"{server_var}.use_middleware({mw_name})")
                
                for route_node in group_routes:
                    method = route_node.get("method", "GET")
                    pattern = route_node.get("pattern", "/")
                    handler = route_node.get("handler", "")
                    handler_type = route_node.get("handler_type", "fn")
                    dag_chain = route_node.get("dag_chain", [])
                    
                    full_pattern = f"{prefix}{pattern}" if prefix else pattern
                    
                    if handler_type == "semantic":
                        self.code.append(f"{server_var}.semantic_route('{full_pattern}', '{handler}')")
                    elif handler_type == "dag":
                        dag_str = json.dumps(dag_chain, ensure_ascii=False)
                        self.code.append(f"{server_var}.route('{method}', '{full_pattern}', '{handler}', handler_type='dag', dag_chain={dag_str})")
                    elif handler_type == "agent":
                        self.code.append(f"{server_var}.route('{method}', '{full_pattern}', '{handler}', handler_type='agent')")
                    else:
                        self.code.append(f"{server_var}.route('{method}', '{full_pattern}', '{handler}')")
            
            # Register agents for agent/dag/semantic routes
            agent_names_in_routes = set()
            for route_node in routes:
                handler_type = route_node.get("handler_type", "fn")
                handler = route_node.get("handler", "")
                if handler_type in ("agent", "semantic", "dag"):
                    agent_names_in_routes.add(handler)
                    for dag_agent in route_node.get("dag_chain", []):
                        agent_names_in_routes.add(dag_agent)
            for group in groups:
                for route_node in group.get("routes", []):
                    handler_type = route_node.get("handler_type", "fn")
                    handler = route_node.get("handler", "")
                    if handler_type in ("agent", "semantic", "dag"):
                        agent_names_in_routes.add(handler)
                        for dag_agent in route_node.get("dag_chain", []):
                            agent_names_in_routes.add(dag_agent)
            
            for agent_name in sorted(agent_names_in_routes):
                # Use the generated agent variable name
                self.code.append(f"{server_var}.register_agent('{agent_name}', agent_{agent_name})")
            
            self.code.append("")
            self.code.append(f"# Start HTTP server on port {port}")
            self.code.append(f"print(f'🚀 Nexa HTTP Server: http://0.0.0.0:{port}')")
            self.code.append(f"print(f'   Routes: {{{server_var}.state.route_count()}}  |  Static: {{{server_var}.state.static_dir_count()}}')")
            self.code.append("")
    
    def _generate_flow_stmt_code(self, stmt, indent=0):
        """将 flow_stmt AST 节点转换为 Python 代码行
        
        Used in Job perform/on_failure body code generation.
        """
        prefix = "    " * indent
        if not isinstance(stmt, dict):
            return str(stmt) if stmt else None
        
        stmt_type = stmt.get("type", "")
        
        if stmt_type == "assignment_stmt":
            target = stmt.get("target", "")
            value = stmt.get("value", "")
            if isinstance(value, dict):
                value_code = self._generate_expr_code(value)
                return f"{target} = {value_code}"
            return f"{target} = {value}"
        
        elif stmt_type == "expr_stmt":
            expr = stmt.get("expression", stmt.get("expr", ""))
            if isinstance(expr, dict):
                expr_code = self._generate_expr_code(expr)
                return f"{expr_code}"
            return f"{expr}"
        
        elif stmt_type == "print_stmt":
            expr = stmt.get("expression", stmt.get("expr", ""))
            if isinstance(expr, dict):
                expr_code = self._generate_expr_code(expr)
                return f"print({expr_code})"
            return f"print({expr})"
        
        elif stmt_type == "method_call":
            obj = stmt.get("object", stmt.get("agent", ""))
            method = stmt.get("method", "")
            args = stmt.get("arguments", [])
            args_str = ", ".join([self._generate_expr_code(a) if isinstance(a, dict) else str(a) for a in args])
            return f"{obj}.{method}({args_str})"
        
        elif stmt_type == "id_expr":
            return stmt.get("value", stmt.get("name", ""))
        
        elif stmt_type == "InterpolatedString":
            return self._generate_interpolated_string(stmt.get("parts", []))
        elif stmt_type == "string_expr":
            return f'"{stmt.get("value", "")}"'
        
        elif stmt_type == "int_expr":
            return str(stmt.get("value", 0))
        
        elif stmt_type == "Assignment":
            target = stmt.get("target", "")
            value = stmt.get("value", "")
            if isinstance(value, dict):
                value_code = self._generate_expr_code(value)
                return f"{target} = {value_code}"
            return f"{target} = {value}"
        
        elif stmt_type == "ExpressionStatement":
            expr = stmt.get("expression", stmt)
            if isinstance(expr, dict):
                return self._generate_expr_code(expr)
            return str(expr)
        
        elif stmt_type == "PrintStatement":
            expr = stmt.get("expression", "")
            if isinstance(expr, dict):
                expr_code = self._generate_expr_code(expr)
                return f"print({expr_code})"
            return f"print({expr})"
        
        # 默认:尝试递归处理
        for key in ["expression", "value", "expr"]:
            if key in stmt and isinstance(stmt[key], dict):
                return self._generate_expr_code(stmt[key])
        
        return None
    
    def _generate_expr_code(self, expr):
        """将表达式 AST 节点转换为 Python 代码字符串"""
        if not isinstance(expr, dict):
            return str(expr) if expr else ""
        
        expr_type = expr.get("type", "")
        
        # P2-4: Template expression code generation
        if expr_type == "TemplateStringExpr":
            return self._generate_template_expr(expr.get("parts", []))
        
        # P3-1: Interpolated string code generation
        if expr_type == "InterpolatedString":
            return self._generate_interpolated_string(expr.get("parts", []))
        
        if expr_type == "method_call":
            obj = expr.get("object", expr.get("agent", ""))
            method = expr.get("method", "")
            args = expr.get("arguments", [])
            args_str = ", ".join([self._generate_expr_code(a) if isinstance(a, dict) else str(a) for a in args])
            return f"{obj}.{method}({args_str})"
        
        elif expr_type == "id_expr" or expr_type == "IdExpr":
            return expr.get("value", expr.get("name", ""))
        
        elif expr_type == "string_expr" or expr_type == "StringExpr":
            val = expr.get("value", "")
            return f'"{val}"'
        
        elif expr_type == "int_expr" or expr_type == "IntExpr":
            return str(expr.get("value", 0))
        
        elif expr_type == "float_expr" or expr_type == "FloatExpr":
            return str(expr.get("value", 0.0))
        
        elif expr_type == "property_access" or expr_type == "PropertyAccess":
            obj = expr.get("object", expr.get("name", ""))
            prop = expr.get("property", expr.get("field", ""))
            return f"{obj}.{prop}"
        
        elif expr_type == "pipeline_expr":
            left = self._generate_expr_code(expr.get("left", ""))
            right = self._generate_expr_code(expr.get("right", ""))
            return f"{left} >> {right}"
        
        elif expr_type in ("dict_access_expr", "DictAccessExpr"):
            obj = self._generate_expr_code(expr.get("object", ""))
            key = self._generate_expr_code(expr.get("key", ""))
            return f"{obj}[{key}]"
        
        # 默认
        if "value" in expr:
            return str(expr["value"])
        if "name" in expr:
            return expr["name"]
        
        return str(expr)

    # ===== P2-4: Template System Code Generation =====

    def _generate_template_expr(self, parts: list) -> str:
        '''Generate Python code for a template expression (TemplateStringExpr)

        Generates inline Python code that renders the template parts:
        - Literal: append string literal
        - Expr: append escaped variable value
        - RawExpr: append unescaped variable value
        - FilteredExpr: append filtered + escaped value
        - RawFilteredExpr: append filtered unescaped value
        - ForLoop: Python for-loop with metadata bindings
        - IfBlock: Python if/elif/else chain
        - Partial: _nexa_tpl_partial() call

        Returns a Python expression string that evaluates to the rendered template output
        '''
        # Build list of append statements
        lines = []
        lines.append('_nexa_tpl_join([__r for __r in (')
        
        for part in parts:
            kind = part.get('kind', 'literal')
            
            if kind == 'literal':
                value = part.get('value', '')
                # Escape for Python string literal
                escaped = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')
                lines.append(f"  '{escaped}',")
            
            elif kind == 'expr':
                var_name = part.get('value', '')
                lines.append(f"  _nexa_tpl_escape(_nexa_tpl_safe_str({self._tpl_var_access(var_name)})),")
            
            elif kind == 'raw_expr':
                var_name = part.get('value', '')
                lines.append(f"  _nexa_tpl_safe_str({self._tpl_var_access(var_name)}),")
            
            elif kind == 'filtered_expr':
                var_name = part.get('value', '')
                filters = part.get('filters', [])
                chain = self._tpl_filter_chain(var_name, filters)
                lines.append(f"  _nexa_tpl_escape({chain}),")
            
            elif kind == 'raw_filtered_expr':
                var_name = part.get('value', '')
                filters = part.get('filters', [])
                chain = self._tpl_filter_chain(var_name, filters)
                lines.append(f"  {chain},")
            
            elif kind == 'for_loop':
                for_code = self._tpl_for_loop(part)
                lines.append(f"  {for_code},")
            
            elif kind == 'if_block':
                if_code = self._tpl_if_block(part)
                lines.append(f"  {if_code},")
            
            elif kind == 'partial':
                partial_name = part.get('partial_name', '')
                data_expr = part.get('data_expr', '')
                if data_expr:
                    lines.append(f"  _nexa_tpl_partial('{partial_name}', {self._tpl_var_access(data_expr)}),")
                else:
                    lines.append(f"  _nexa_tpl_partial('{partial_name}'),")
        
        lines.append('])')
        return '\n'.join(lines)

    def _tpl_var_access(self, var_name: str) -> str:
        'Convert template variable name to Python variable access (supports dot notation)'
        if not var_name:
            return 'None'
        if var_name.startswith('@'):
            # Loop metadata variable
            return var_name
        # Simple variable or dot-access
        parts = var_name.split('.')
        if len(parts) == 1:
            return var_name
        # Generate dict-style access: user.name -> user["name"]
        base = parts[0]
        result = base
        for p in parts[1:]:
            result = f'{result}["{p}"]'
        return result

    def _tpl_filter_chain(self, var_name: str, filters: list) -> str:
        'Generate filter chain Python code: _nexa_tpl_filter_xxx(var, args...)'
        result = f'_nexa_tpl_safe_str({self._tpl_var_access(var_name)})'
        for f in filters:
            fname = f.get('name', '')
            fargs = f.get('args', [])
            # Map filter name to _nexa_tpl_filter_xxx function
            func_name = f'_nexa_tpl_filter_{fname}'
            if fargs:
                args_str = ', '.join([str(a) if isinstance(a, (int, float)) else f"'{a}'" for a in fargs])
                result = f'{func_name}({result}, {args_str})'
            else:
                result = f'{func_name}({result})'
        return result

    def _tpl_for_loop(self, part: dict) -> str:
        'Generate Python for-loop code for template ForLoop'
        # Delegate to render_string which handles all cases (with/without empty_body)
        return f'render_string({json.dumps(part)}, locals())'

    def _tpl_if_block(self, part: dict) -> str:
        'Generate Python if/elif/else code for template IfBlock'
        condition = part.get('condition', '')
        then_parts = part.get('body', [])
        elif_chains = part.get('elif_chains', [])
        else_parts = part.get('else_parts', [])
        
        # For simplicity, delegate to render_string which handles all cases
        return f'render_string({json.dumps(part)}, locals())'

    # ===== P3-1: String Interpolation Code Generation =====

    def _generate_interpolated_string(self, parts: list) -> str:
        'P3-1: Generate Python code for an InterpolatedString AST node.\n\nGenerates a concatenation expression using _nexa_interp_str() for expression parts.\nFor literal parts: direct string constant.\nFor expr parts: _nexa_interp_str(expr_value) wrapping.\n\nExample: "Hello #{name}!" -> \'Hello \' + _nexa_interp_str(name) + \'!\''
        if not parts:
            return '""'
        
        segments = []
        for part in parts:
            kind = part.get('kind', 'literal')
            value = part.get('value', '')
            
            if kind == 'literal':
                # Literal string part — escape for Python string literal
                escaped = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')
                segments.append(f"'{escaped}'")
            elif kind == 'expr':
                if not value:
                    # Empty interpolation #{} -> empty string
                    segments.append("''")
                else:
                    # Expression part — convert variable/access to Python and wrap with _nexa_interp_str
                    expr_python = self._interp_expr_to_python(value)
                    segments.append(f"_nexa_interp_str({expr_python})")
        
        if not segments:
            return '""'
        if len(segments) == 1:
            return segments[0]
        return ' + '.join(segments)

    def _interp_expr_to_python(self, expr_str: str) -> str:
        'P3-1: Convert a simple interpolation expression string to Python code.\n\nSupports:\n- Simple identifier: name -> name\n- Dot access: user.name -> user["name"]\n- Bracket access: arr[0] -> arr[0], dict["key"] -> dict["key"]'
        if '.' in expr_str or '[' in expr_str:
            # Parse dot and bracket access
            # Split by . first, then handle brackets
            parts = []
            remaining = expr_str
            while remaining:
                # Find next . or [
                dot_idx = remaining.find('.')
                bracket_idx = remaining.find('[')
                
                if dot_idx == -1 and bracket_idx == -1:
                    parts.append(remaining)
                    break
                
                # Determine which comes first
                if bracket_idx != -1 and (dot_idx == -1 or bracket_idx < dot_idx):
                    # Bracket access comes first
                    base = remaining[:bracket_idx]
                    if base:
                        parts.append(base)
                    # Find matching ]
                    close_idx = remaining.find(']', bracket_idx)
                    if close_idx != -1:
                        key_content = remaining[bracket_idx + 1:close_idx]
                        parts.append(f'[{key_content}]')
                        remaining = remaining[close_idx + 1:]
                        # If remaining starts with ., skip it
                        if remaining.startswith('.'):
                            remaining = remaining[1:]
                    else:
                        parts.append(remaining)
                        break
                else:
                    # Dot access comes first
                    base = remaining[:dot_idx]
                    if base:
                        parts.append(base)
                    attr = remaining[dot_idx + 1:]
                    # Check if attr has more . or [
                    next_dot = attr.find('.')
                    next_bracket = attr.find('[')
                    if next_dot == -1 and next_bracket == -1:
                        parts.append(attr)
                        remaining = ''
                    else:
                        # Find the end of this attribute name
                        end_idx = min(
                            idx for idx in [next_dot, next_bracket] if idx != -1
                        )
                        parts.append(attr[:end_idx])
                        remaining = attr[end_idx:]
            
            # Build Python expression: first part is identifier, subsequent are dict/list access
            result = parts[0]
            for p in parts[1:]:
                if p.startswith('['):
                    result += p
                else:
                    result += f'["{p}"]'
            return result
        else:
            # Simple identifier
            return expr_str

    def _generate_flows(self):
        for flow in self.flows:
            name = flow["name"]
            requires_clauses = flow.get("requires", [])
            ensures_clauses = flow.get("ensures", [])
            return_type = flow.get("return_type")  # v1.1: 返回类型
            
            # Generate flow function with parameters
            params = flow.get("params", [])
            # v1.1: 参数带类型标注注释
            param_str = ", ".join([p["name"] for p in params]) if params else ""
            self.code.append(f'def flow_{name}({param_str}):')
            self.indent_level += 1
            
            # v1.1: 渐进式类型系统 — 参数类型检查
            if params:
                for p in params:
                    type_annotation = p.get("type_annotation")
                    if type_annotation and isinstance(type_annotation, dict):
                        # 生成类型注释: # Type: param_name: type_str
                        type_str = self._type_expr_to_python_type(type_annotation)
                        self.code.append(f'{self._indent()}# Type: {p["name"]}: {type_str}')
                        # 生成运行时类型检查代码 (根据 NEXA_TYPE_MODE 决定行为)
                        type_ctor = self._type_expr_to_constructor(type_annotation)
                        self.code.append(self._indent() + '__type_check_' + p['name'] + ' = __type_checker.check_type_match(' + p['name'] + ', ' + type_ctor + ', context={"function": "' + name + '", "param": "' + p['name'] + '"})')
                        self.code.append(f'{self._indent()}__type_checker.handle_violation(__type_check_{p["name"]})')
            
            # v1.1: 返回类型注释
            if return_type and isinstance(return_type, dict):
                ret_type_str = self._type_expr_to_python_type(return_type)
                self.code.append(f'{self._indent()}# Type: return {ret_type_str}')
            
            # Design by Contract: 生成契约检查代码
            if requires_clauses or ensures_clauses:
                # 生成契约规格变量
                contract_var = f"__contract_{name}"
                self._generate_flow_contract(contract_var, requires_clauses, ensures_clauses)
                
                # requires 检查
                if requires_clauses:
                    # 构造上下文 dict(包含所有参数)
                    if params:
                        context_items = ", ".join([f'"{p["name"]}": {p["name"]}' for p in params])
                        self.code.append(f'{self._indent()}__ctx = {{ {context_items} }}')
                    else:
                        self.code.append(f'{self._indent()}__ctx = {{}}')
                    self.code.append(f'{self._indent()}__req_violation = check_requires({contract_var}, __ctx)')
                    self.code.append(f'{self._indent()}if __req_violation:')
                    self.indent_level += 1
                    self.code.append(f'{self._indent()}raise ContractViolation(__req_violation.args[0], clause_type=__req_violation.clause_type, clause=__req_violation.clause, context=__req_violation.context, is_semantic=__req_violation.is_semantic)')
                    self.indent_level -= 1
                
                # 捕获 old() 值
                if ensures_clauses:
                    self.code.append(f'{self._indent()}__old_values = capture_old_values({contract_var}, __ctx if requires_clauses else {{}})')
            
            # P3-5: Check for defer statements in flow body
            has_defers = any(
                isinstance(stmt, dict) and stmt.get("type") == "DeferStatement"
                for stmt in flow["body"]
            )
            
            if has_defers:
                self.code.append(f'{self._indent()}_nexa_defer_stack = []')
                self.code.append(f'{self._indent()}try:')
                self.indent_level += 1
            
            # Generate body statements
            for stmt in flow["body"]:
                self._generate_statement(stmt)
            
            if has_defers:
                self.indent_level -= 1
                self.code.append(f'{self._indent()}finally:')
                self.indent_level += 1
                self.code.append(f'{self._indent()}_nexa_defer_execute(_nexa_defer_stack)')
                self.indent_level -= 1
            
            # Design by Contract: ensures 检查(对 flow 的最后赋值结果进行检查)
            if ensures_clauses:
                # 尝试获取 result(flow 的隐式返回值)
                self.code.append(f'{self._indent()}__flow_result = locals().get("__result", None) or locals().get("result", None)')
                if requires_clauses:
                    self.code.append(f'{self._indent()}__ens_violation = check_ensures({contract_var}, __ctx, __flow_result, __old_values)')
                else:
                    self.code.append(f'{self._indent()}__ens_violation = check_ensures({contract_var}, {{}}, __flow_result, __old_values)')
                self.code.append(f'{self._indent()}if __ens_violation:')
                self.indent_level += 1
                self.code.append(f'{self._indent()}raise ContractViolation(__ens_violation.args[0], clause_type=__ens_violation.clause_type, clause=__ens_violation.clause, context=__ens_violation.context, is_semantic=__ens_violation.is_semantic)')
                self.indent_level -= 1
            
            self.indent_level -= 1
            self.code.append("")
    
    def _generate_contract_spec(self, owner_name: str, requires_clauses: list, ensures_clauses: list) -> str:
        """生成 ContractSpec 对象的 Python 代码字符串
        
        Args:
            owner_name: agent/flow 名称(用于变量命名)
            requires_clauses: requires 契约条款列表
            ensures_clauses: ensures 契约条款列表
        
        Returns:
            Python 表达式字符串,如 "ContractSpec(requires=[...], ensures=[...])"
            如果没有契约条款,返回空字符串 ""
        """
        if not requires_clauses and not ensures_clauses:
            return ""
        
        req_items = []
        for clause in requires_clauses:
            req_items.append(self._generate_contract_clause(clause))
        
        ens_items = []
        for clause in ensures_clauses:
            ens_items.append(self._generate_contract_clause(clause))
        
        req_str = ", ".join(req_items)
        ens_str = ", ".join(ens_items)
        
        return f"ContractSpec(requires=[{req_str}], ensures=[{ens_str}])"
    
    def _generate_contract_clause(self, clause: dict) -> str:
        """生成单个 ContractClause 的 Python 代码字符串
        
        Args:
            clause: 契约条款字典(来自 AST)
        
        Returns:
            Python 表达式字符串,如 "ContractClause(expression='amount > 0', is_semantic=False)"
        """
        is_semantic = clause.get("is_semantic", False)
        clause_type = clause.get("clause_type", "requires")
        
        if is_semantic:
            condition_text = clause.get("condition_text", "")
            # 对字符串进行安全转义
            escaped = condition_text.replace("\\", "\\\\").replace('"', '\\"')
            return f'ContractClause(condition_text="{escaped}", is_semantic=True, clause_type="{clause_type}")'
        else:
            expression = clause.get("expression", "")
            # 对表达式字符串进行安全转义
            escaped = expression.replace("\\", "\\\\").replace('"', '\\"')
            return f'ContractClause(expression="{escaped}", is_semantic=False, clause_type="{clause_type}")'
    
    def _generate_flow_contract(self, contract_var: str, requires_clauses: list, ensures_clauses: list):
        """为 flow 函数生成契约规格变量
        
        Args:
            contract_var: 契约变量名(如 "__contract_process_payment")
            requires_clauses: requires 契约条款列表
            ensures_clauses: ensures 契约条款列表
        """
        if not requires_clauses and not ensures_clauses:
            return
        
        req_items = []
        for clause in requires_clauses:
            req_items.append(self._generate_contract_clause(clause))
        
        ens_items = []
        for clause in ensures_clauses:
            ens_items.append(self._generate_contract_clause(clause))
        
        req_str = ", ".join(req_items)
        ens_str = ", ".join(ens_items)
        
        self.code.append(f'{self._indent()}{contract_var} = ContractSpec(requires=[{req_str}], ensures=[{ens_str}])')


    # ===== P3-3: Pattern Matching Code Generation =====

    def _generate_match_expr(self, stmt):
        'Generate Python if/elif chain for match expression with pattern matching'
        scrutinee = stmt.get('scrutinee', {})
        arms = stmt.get('arms', [])
        
        scrutinee_code = self._resolve_expression(scrutinee)
        self.code.append(f'{self._indent()}_match_value = {scrutinee_code}')
        self.code.append(f'{self._indent()}_match_result = None')
        
        first = True
        for arm in arms:
            pattern = arm.get('pattern', {})
            body = arm.get('body', [])
            guard = arm.get('guard', None)
            
            # Generate pattern condition check
            condition_code = self._generate_pattern_condition(pattern, '_match_value')
            
            if guard is not None:
                guard_code = self._resolve_expression(guard)
                condition_code = f'{condition_code} and {guard_code}'
            
            if first:
                self.code.append(f'{self._indent()}if {condition_code}:')
                first = False
            else:
                self.code.append(f'{self._indent()}elif {condition_code}:')
            
            self.indent_level += 1
            # Generate variable bindings from pattern
            self._generate_pattern_bindings(pattern, '_match_value')
            # Generate body
            if isinstance(body, dict):
                # Body is an expression (not a block)
                body_code = self._resolve_expression(body)
                self.code.append(f'{self._indent()}_match_result = {body_code}')
            elif isinstance(body, list):
                # Body is a block of statements
                for sub_stmt in body:
                    self._generate_statement(sub_stmt)
                # Try to capture result from body statements
                self.code.append(f'{self._indent()}_match_result = locals().get("_match_expr_result", locals().get("result", _match_value))')
            self.indent_level -= 1
        
        self.indent_level += 1
        self.code.append('')
        self.indent_level -= 1

    def _generate_pattern_condition(self, pattern, value_var):
        'Generate Python condition expression for pattern matching'
        kind = pattern.get('kind', '')
        
        if kind == 'wildcard':
            return 'True'
        
        elif kind == 'variable':
            # Variable always matches
            return 'True'
        
        elif kind == 'literal':
            pat_value = pattern.get('value')
            value_type = pattern.get('value_type', '')
            if value_type == 'string':
                return f'{value_var} == "{pat_value}"'
            elif value_type == 'bool':
                if pat_value:
                    return f'{value_var} == True'
                else:
                    return f'{value_var} == False'
            else:
                return f'{value_var} == {pat_value}'
        
        elif kind == 'tuple':
            elements = pattern.get('elements', [])
            length = len(elements)
            return f'_nexa_is_tuple_like({value_var}, {length})'
        
        elif kind == 'array':
            elements = pattern.get('elements', [])
            rest = pattern.get('rest')
            min_len = len(elements)
            if rest is None:
                return f'_nexa_is_tuple_like({value_var}, {min_len})'
            else:
                return f'_nexa_is_list_like({value_var}, {min_len})'
        
        elif kind == 'map':
            entries = pattern.get('entries', [])
            required_keys = [e.get('key') for e in entries]
            keys_str = json.dumps(required_keys)
            return f'_nexa_is_dict_with_keys({value_var}, {keys_str})'
        
        elif kind == 'variant':
            enum_name = pattern.get('enum_name', '')
            variant_name = pattern.get('variant_name', '')
            return f'_nexa_is_variant({value_var}, "{enum_name}", "{variant_name}")'
        
        return 'True'

    def _generate_pattern_bindings(self, pattern, value_var, depth=0):
        'Generate Python variable binding code from pattern match'
        kind = pattern.get('kind', '')
        
        if kind == 'wildcard':
            # No binding
            pass
        
        elif kind == 'variable':
            name = pattern.get('name', '')
            self.code.append(f'{self._indent()}{name} = {value_var}')
        
        elif kind == 'literal':
            # No binding for literal patterns
            pass
        
        elif kind == 'tuple':
            elements = pattern.get('elements', [])
            for i, elem in enumerate(elements):
                self._generate_pattern_bindings(elem, f'{value_var}[{i}]', depth + 1)
        
        elif kind == 'array':
            elements = pattern.get('elements', [])
            rest = pattern.get('rest')
            for i, elem in enumerate(elements):
                self._generate_pattern_bindings(elem, f'{value_var}[{i}]', depth + 1)
            if rest is not None:
                min_len = len(elements)
                self.code.append(f'{self._indent()}{rest} = _nexa_list_rest({value_var}, {min_len})')
        
        elif kind == 'map':
            entries = pattern.get('entries', [])
            rest = pattern.get('rest')
            for entry in entries:
                key = entry.get('key', '')
                vp = entry.get('value_pattern')
                if vp is not None:
                    self._generate_pattern_bindings(vp, f'{value_var}["{key}"]', depth + 1)
                else:
                    # Shorthand: {name} binds value["name"] to variable name
                    self.code.append(f'{self._indent()}{key} = {value_var}["{key}"]')
            if rest is not None:
                required_keys = [e.get('key') for e in entries]
                keys_str = json.dumps(required_keys)
                self.code.append(f'{self._indent()}{rest} = _nexa_dict_rest({value_var}, {keys_str})')
        
        elif kind == 'variant':
            fields = pattern.get('fields', [])
            for i, field in enumerate(fields):
                self._generate_pattern_bindings(field, f'{value_var}["_nexa_fields"][{i}]', depth + 1)

    def _generate_let_pattern(self, stmt):
        'Generate Python code for let destructuring: let pattern = expr;'
        pattern = stmt.get('pattern', {})
        expression = stmt.get('expression', {})
        
        expr_code = self._resolve_expression(expression)
        
        # Generate: _let_value = expr; then pattern bindings
        self.code.append(f'{self._indent()}_let_value = {expr_code}')
        self._generate_pattern_bindings(pattern, '_let_value')

    def _generate_for_pattern(self, stmt):
        'Generate Python code for for destructuring: for pattern in expr block'
        pattern = stmt.get('pattern', {})
        iterable = stmt.get('iterable', {})
        body = stmt.get('body', [])
        
        iterable_code = self._resolve_expression(iterable)
        
        self.code.append(f'{self._indent()}for _for_item in {iterable_code}:')
        self.indent_level += 1
        self._generate_pattern_bindings(pattern, '_for_item')
        for sub_stmt in body:
            self._generate_statement(sub_stmt)
        self.indent_level -= 1

    def _generate_tests(self):
        for t in self.tests:
            name = t["name"].replace(' ', '_').replace('-', '_').replace('.', '_')
            self.code.append(f'def test_{name}():')
            self.indent_level += 1
            for stmt in t["body"]:
                self._generate_statement(stmt)
            self.indent_level -= 1
            self.code.append("")

    def _generate_statement(self, stmt):
        st_type = stmt.get("type")
        
        # ===== P3-4: ADT — Struct/Enum/Trait/Impl (代数数据类型) =====
        if st_type == "StructDeclaration":
            # Struct declarations are registered at top level, but may appear as statements
            name = stmt.get('name', '')
            fields = stmt.get('fields', [])
            field_strs = []
            for f in fields:
                f_name = f.get('name', '')
                f_type = f.get('field_type', None)
                if f_type:
                    field_strs.append("{'name': '" + f_name + "', 'type': '" + f_type + "'}")
                else:
                    field_strs.append("{'name': '" + f_name + "'}")
            fields_arg = '[' + ', '.join(field_strs) + ']'
            self.code.append(self._indent() + "register_struct('" + name + "', " + fields_arg + ")")
        
        elif st_type == "EnumDeclaration":
            name = stmt.get('name', '')
            variants = stmt.get('variants', [])
            variant_strs = []
            for v in variants:
                v_name = v.get('name', '')
                v_fields = v.get('fields', [])
                fields_str = '[' + ', '.join("'" + f + "'" for f in v_fields) + ']'
                variant_strs.append("{'name': '" + v_name + "', 'fields': " + fields_str + "}")
            variants_arg = '[' + ', '.join(variant_strs) + ']'
            self.code.append(self._indent() + "register_enum('" + name + "', " + variants_arg + ")")
        
        elif st_type == "TraitDeclaration":
            name = stmt.get('name', '')
            methods = stmt.get('methods', [])
            method_strs = []
            for m in methods:
                m_name = m.get('name', '')
                m_params = m.get('params', [])
                m_return = m.get('return_type', None)
                param_strs = []
                for p in m_params:
                    if isinstance(p, dict):
                        p_name = p.get('name', p.get('value', ''))
                        param_strs.append("'" + p_name + "'")
                    else:
                        param_strs.append("'" + str(p) + "'")
                params_arg = '[' + ', '.join(param_strs) + ']'
                return_arg = "'" + m_return + "'" if m_return else 'None'
                method_strs.append("{'name': '" + m_name + "', 'params': " + params_arg + ", 'return_type': " + return_arg + "}")
            methods_arg = '[' + ', '.join(method_strs) + ']'
            self.code.append(self._indent() + "register_trait('" + name + "', " + methods_arg + ")")
        
        elif st_type == "ImplDeclaration":
            trait_name = stmt.get('trait_name', '')
            type_name = stmt.get('type_name', '')
            methods = stmt.get('methods', [])
            method_entries = []
            for m in methods:
                m_name = m.get('name', '')
                m_body = m.get('body', [])
                body_code = self._generate_impl_method_body(m_body)
                method_entries.append("'" + m_name + "': " + body_code)
            methods_arg = '{' + ', '.join(method_entries) + '}'
            self.code.append(f"{self._indent()}register_impl('{trait_name}', '{type_name}', {methods_arg})")

        # ===== P3-3: Pattern Matching (模式匹配) =====
        elif st_type == "MatchExpression":
            self._generate_match_expr(stmt)
        
        elif st_type == "LetPatternStatement":
            self._generate_let_pattern(stmt)
        
        elif st_type == "ForPatternStatement":
            self._generate_for_pattern(stmt)
        
        # ===== P3-5: Defer Statement (延迟执行) =====
        elif st_type == "DeferStatement":
            expr_str = self._resolve_expression(stmt["expression"])
            self.code.append(f"{self._indent()}_nexa_defer_stack.append(lambda: {expr_str})")
        
        # ===== v1.2: Error Propagation (? 操作符 + otherwise 内联错误处理) =====
        elif st_type == "TryAssignmentStatement":
            # x = expr?  ->  错误传播赋值
            # 生成: target = propagate_or_else(expr_value)
            # 如果 expr 是 Agent 调用,使用 run_result() 代替 run()
            target = stmt["target"]
            expr_str = self._resolve_try_op_expression(stmt["expression"])
            self.code.append(f"{self._indent()}{target} = {expr_str}")
            
        elif st_type == "OtherwiseAssignmentStatement":
            # x = expr otherwise handler  ->  内联错误处理赋值
            # 生成: target = propagate_or_else(expr_value, otherwise_handler_code)
            target = stmt["target"]
            expr_str = self._resolve_expression(stmt["expression"])
            # 如果 expr 是 Agent.run(),改为 Agent.run_result() 以获取 NexaResult
            expr_str = self._agent_run_to_run_result(expr_str)
            handler_code = self._resolve_otherwise_handler(stmt["otherwise_handler"])
            self.code.append(f"{self._indent()}{target} = propagate_or_else({expr_str}, {handler_code})")
            
        elif st_type == "TryExprStatement":
            # expr?  ->  错误传播(无赋值)
            # 生成: propagate_or_else(expr_value)
            expr_str = self._resolve_try_op_expression(stmt["expression"])
            self.code.append(f"{self._indent()}propagate_or_else({expr_str})")
        
        elif st_type == "AssignmentStatement":
            target = stmt["target"]
            value = stmt["value"]
            # P3-3: If value is a MatchExpression, generate match code then assign result
            if isinstance(value, dict) and value.get("type") == "MatchExpression":
                self._generate_match_expr(value)
                self.code.append(f"{self._indent()}{target} = _match_result")
            else:
                val_str = self._resolve_expression(value)
                self.code.append(f"{self._indent()}{target} = {val_str}")
            
        elif st_type == "ExpressionStatement":
            val_str = self._resolve_expression(stmt["expression"])
            self.code.append(f"{self._indent()}{val_str}")

        elif st_type == "AssertStatement":
            val_str = self._resolve_expression(stmt["expression"])
            self.code.append(f"{self._indent()}assert {val_str}")
            
        elif st_type == "BreakStatement":
            self.code.append(f"{self._indent()}break")
            
        elif st_type == "SemanticIfStatement":
            cond = stmt["condition"]
            fast_match = stmt.get("fast_match")
            target = stmt["target_variable"]
            
            if fast_match:
                # pass fast_match as third arg
                self.code.append(f"{self._indent()}if nexa_semantic_eval(\"{cond}\", {target}, r\"{fast_match}\"):")
            else:
                self.code.append(f"{self._indent()}if nexa_semantic_eval(\"{cond}\", {target}):")
            
            self.indent_level += 1
            for sub_stmt in stmt.get("consequence", []):
                 self._generate_statement(sub_stmt)
            self.indent_level -= 1
            
            alt = stmt.get("alternative", [])
            if alt:
                self.code.append(f"{self._indent()}else:")
                self.indent_level += 1
                for sub_stmt in alt:
                    self._generate_statement(sub_stmt)
                self.indent_level -= 1

        elif st_type == "MatchIntentStatement":
            target = stmt["target"]
            intents = [case["intent"] for case in stmt["cases"]]
            intents_str = "[ " + ", ".join([f'"{i}"' for i in intents]) + "]"
            
            self.code.append(f"{self._indent()}__matched_intent = nexa_intent_routing({intents_str}, {target})")
            for i, case in enumerate(stmt["cases"]):
                if i == 0:
                    self.code.append(f"{self._indent()}if __matched_intent == \"{case['intent']}\":")
                else:
                    self.code.append(f"{self._indent()}elif __matched_intent == \"{case['intent']}\":")
                
                self.indent_level += 1
                self._generate_statement({"type": "ExpressionStatement", "expression": case["expression"]})
                self.indent_level -= 1
                
            if stmt.get("default"):
                self.code.append(f"{self._indent()}else:")
                self.indent_level += 1
                self._generate_statement({"type": "ExpressionStatement", "expression": stmt["default"]["expression"]})
                self.indent_level -= 1

        elif st_type == "LoopUntilStatement":
            # 初始化循环元数据 - 使用 runtime.meta
            self.code.append(f"{self._indent()}set_loop_count(0)")
            self.code.append(f"{self._indent()}set_last_result(None)")
            self.code.append(f"{self._indent()}while True:")
            self.indent_level += 1
            # 循环开始时增加计数器
            self.code.append(f"{self._indent()}set_loop_count(get_loop_count() + 1)")
            for sub_stmt in stmt["body"]:
                self._generate_statement(sub_stmt)
            cond_str = self._resolve_expression(stmt["condition"])
            self.code.append(f"{self._indent()}if nexa_semantic_eval({cond_str}, str(locals())):")
            self.indent_level += 1
            self.code.append(f"{self._indent()}break")
            self.indent_level -= 2
            self.code.append(f"")

        elif st_type == "TryCatchStatement":
            self.code.append(f"{self._indent()}try:")
            self.indent_level += 1
            for sub_stmt in stmt["block_try"]:
                self._generate_statement(sub_stmt)
            self.indent_level -= 1
            catch_err = stmt["catch_err"]
            self.code.append(f"{self._indent()}except Exception as {catch_err}:")
            self.indent_level += 1
            for sub_stmt in stmt["block_catch"]:
                self._generate_statement(sub_stmt)
            self.indent_level -= 1

        # ===== v1.0.1-beta: 传统控制流 =====
        elif st_type == "TraditionalIfStatement":
            # 传统 if/else if/else
            cond_str = self._resolve_condition(stmt["condition"])
            self.code.append(f"{self._indent()}if {cond_str}:")
            self.indent_level += 1
            for sub_stmt in stmt.get("then_block", []):
                self._generate_statement(sub_stmt)
            self.indent_level -= 1
            
            # else if 子句
            for else_if in stmt.get("else_if_clauses", []):
                cond_str = self._resolve_condition(else_if["condition"])
                self.code.append(f"{self._indent()}elif {cond_str}:")
                self.indent_level += 1
                for sub_stmt in else_if.get("block", []):
                    self._generate_statement(sub_stmt)
                self.indent_level -= 1
            
            # else 子句
            if stmt.get("else_block"):
                self.code.append(f"{self._indent()}else:")
                self.indent_level += 1
                for sub_stmt in stmt["else_block"]:
                    self._generate_statement(sub_stmt)
                self.indent_level -= 1

        elif st_type == "ForEachStatement":
            # for each 循环
            iterator = stmt["iterator"]
            iterable_str = self._resolve_expression(stmt["iterable"])
            
            if stmt.get("index"):
                # 带索引: for index, item in enumerate(iterable)
                index = stmt["index"]
                self.code.append(f"{self._indent()}for {index}, {iterator} in enumerate({iterable_str}):")
            else:
                # 简单遍历: for item in iterable
                self.code.append(f"{self._indent()}for {iterator} in {iterable_str}:")
            
            self.indent_level += 1
            for sub_stmt in stmt.get("body", []):
                self._generate_statement(sub_stmt)
            self.indent_level -= 1

        elif st_type == "WhileStatement":
            # while 循环
            cond_str = self._resolve_condition(stmt["condition"])
            self.code.append(f"{self._indent()}while {cond_str}:")
            self.indent_level += 1
            for sub_stmt in stmt.get("body", []):
                self._generate_statement(sub_stmt)
            self.indent_level -= 1

        elif st_type == "ContinueStatement":
            self.code.append(f"{self._indent()}continue")

        elif st_type == "PythonEscapeStatement":
            # Python 逃生舱 - 直接注入 Python 代码
            python_code = stmt.get("code", "")
            if python_code:
                # 按行分割并添加当前缩进
                lines = python_code.split('\n')
                for line in lines:
                    if line.strip():  # 跳过空行
                        self.code.append(f"{self._indent()}{line}")
                    else:
                        self.code.append("")

    def _resolve_condition(self, cond):
        """解析条件表达式 - v1.0.1-beta"""
        if cond is None:
            return "True"
        
        cond_type = cond.get("type")
        
        if cond_type == "ComparisonExpression":
            left = self._resolve_expression(cond["left"])
            op = cond["operator"]
            right = self._resolve_expression(cond["right"])
            return f"{left} {op} {right}"
        
        elif cond_type == "LogicalExpression":
            left = self._resolve_condition(cond["left"])
            op = cond["operator"]
            right = self._resolve_condition(cond["right"])
            return f"({left} {op} {right})"
        
        elif cond_type == "ConditionExpression":
            left = self._resolve_expression(cond["left"])
            op = cond["operator"]
            right = self._resolve_expression(cond["right"])
            return f"{left} {op} {right}"
        
        elif cond_type == "BooleanLiteral":
            return "True" if cond.get("value") else "False"
        
        elif cond_type == "Identifier":
            return cond["value"]
        
        else:
            # 默认处理为表达式
            return self._resolve_expression(cond)

    def _resolve_expression(self, expr):
        ex_type = expr.get("type")
        if ex_type == "KeywordArgument":
            return f'{expr["key"]}={self._resolve_expression(expr["value"])}'
        elif ex_type == "DictAccessExpression":
            base_str = self._resolve_expression(expr["base"])
            key_str = self._resolve_expression(expr["key"])
            return f'{base_str}[{key_str}]'
        # P2-4: Template expression
        elif ex_type == "TemplateStringExpr":
            return self._generate_template_expr(expr.get("parts", []))
        elif ex_type == "InterpolatedString":
            return self._generate_interpolated_string(expr.get("parts", []))
        elif ex_type == "StringLiteral":
            return f'"{expr["value"]}"'
        elif ex_type == "PropertyAccess":
            base = expr["base"]
            if isinstance(base, str):
                base_str = base
            else:
                base_str = self._resolve_expression(base)
            if base_str == "secrets":
                base_str = "nexa_secrets"
            return f'{base_str}.{expr["property"]}'
        elif ex_type == "Identifier":
            if expr["value"] == "secrets":
                return "nexa_secrets"
            return expr["value"]
        # ===== v1.0.1-beta: 新增字面量类型 =====
        elif ex_type == "IntLiteral":
            return str(expr["value"])
        
        elif ex_type == "FloatLiteral":
            return str(expr["value"])
        
        elif ex_type == "BooleanLiteral":
            return "True" if expr["value"] else "False"
        
        elif ex_type == "ComparisonExpression":
            left = self._resolve_expression(expr["left"])
            op = expr["operator"]
            right = self._resolve_expression(expr["right"])
            return f"{left} {op} {right}"
        
        elif ex_type == "LogicalExpression":
            left = self._resolve_expression(expr["left"])
            op = expr["operator"]
            right = self._resolve_expression(expr["right"])
            return f"({left} {op} {right})"
        
        elif ex_type == "BinaryExpression":
            left = self._resolve_expression(expr["left"])
            right = self._resolve_expression(expr["right"])
            op = expr["operator"]
            # 数值运算不需要 str() 转换
            if op in ["+", "-", "*", "/"]:
                return f"({left} {op} {right})"
            return f"str({left}) {op} str({right})"
        elif ex_type == "MethodCallExpression":
            obj = expr["object"]
            method = expr["method"]
            args_str = ", ".join([self._resolve_expression(a) for a in expr.get("arguments", [])])
            return f'{obj}.{method}({args_str})'
        elif ex_type == "FunctionCallExpression":
            func = expr["function"]
            if func == "img":
                func = "nexa_img_loader"
            elif func == "secret":
                # secret("KEY") -> nexa_secrets.get("KEY")
                func = "nexa_secrets.get"
            elif func == "print":
                # print 保持原样
                pass
            else:
                # 检查是否是 flow 调用 - flow 名称需要添加 flow_ 前缀
                flow_names = [f["name"] for f in self.flows]
                if func in flow_names:
                    func = f"flow_{func}"
            args_str = ", ".join([self._resolve_expression(a) for a in expr.get("arguments", [])])
            return f'{func}({args_str})'
        elif ex_type == "PipelineExpression":
            initial_call = self._resolve_expression(expr["stages"][0])
            agent_names = []
            for stage in expr["stages"][1:]:
                if stage["type"] == "Identifier":
                    agent_names.append(stage["value"])
                elif stage["type"] == "MethodCallExpression":
                    agent_names.append(stage["object"]) # just the agent name for now.
            agents_list_str = "[ " + ", ".join(agent_names) + " ]"
            return f"nexa_pipeline({initial_call}, {agents_list_str})"
        elif ex_type == "JoinCallExpression":
            agents_list_str = "[ " + ", ".join([a for a in expr["agents"]]) + "]"
            method = expr.get("method")
            if "arguments" in expr:
                args_str = ", ".join([self._resolve_expression(a) for a in expr.get("arguments", [])])
            else:
                args_str = "''"
                
            join_str = f"join_agents({agents_list_str}, {args_str})"
            if method:
                return f"{method}.run({join_str})"
            return join_str
        
        # ==================== DAG 表达式代码生成 ====================
        elif ex_type == "DAGForkExpression":
            # 分叉表达式: dag_fanout(input, [Agent1, Agent2])
            input_str = self._resolve_expression(expr["input"])
            agents_list_str = "[ " + ", ".join([a for a in expr["agents"]]) + " ]"
            return f"dag_fanout({input_str}, {agents_list_str})"
        
        elif ex_type == "DAGMergeExpression":
            # 合流表达式: dag_merge([results], strategy="concat", merge_agent=Merger)
            # 或 dag_merge(dag_fanout(...), strategy="consensus")
            agents_list_str = "[ " + ", ".join([a for a in expr["agents"]]) + " ]"
            strategy = expr.get("strategy", "concat")
            merger = expr.get("merger")
            if merger:
                if isinstance(merger, dict):
                    merger_str = self._resolve_expression(merger)
                else:
                    merger_str = str(merger)
                return f"dag_merge({agents_list_str}, strategy=\"{strategy}\", merge_agent={merger_str})"
            return f"dag_merge({agents_list_str}, strategy=\"{strategy}\")"
        
        elif ex_type == "DAGBranchExpression":
            # 条件分支表达式: dag_branch(input, condition_fn, true_agent, false_agent)
            input_str = self._resolve_expression(expr["input"])
            true_agent = expr.get("true_agent")
            false_agent = expr.get("false_agent")
            true_agent_str = self._resolve_expression(true_agent) if true_agent else "None"
            false_agent_str = self._resolve_expression(false_agent) if false_agent else "None"
            # 默认条件函数:检查输入是否包含特定关键词
            return f"dag_branch({input_str}, lambda x: True, {true_agent_str}, {false_agent_str})"
        
        elif ex_type == "DAGChainExpression":
            # 链式 DAG 表达式: expr |>> [...] &>> Agent
            # 生成: dag_merge(dag_fanout(input, [Agents]), strategy="concat", merge_agent=Merger)
            fork_expr = expr["fork"]  # DAGForkExpression
            merge_expr = expr["merge"]  # dag_chain_tail
            
            # 解析 fork 部分
            fork_input = self._resolve_expression(fork_expr["input"])
            fork_agents = "[ " + ", ".join([a for a in fork_expr["agents"]]) + " ]"
            fanout_code = f"dag_fanout({fork_input}, {fork_agents})"
            
            # 解析 merge 部分 - merge_expr 可能是 Identifier 或包含 merge agent 的结构
            if isinstance(merge_expr, dict):
                if merge_expr.get("type") == "Identifier":
                    merge_agent = merge_expr["value"]
                else:
                    merge_agent = self._resolve_expression(merge_expr)
            else:
                merge_agent = str(merge_expr)
            
            return f"dag_merge({fanout_code}, strategy=\"concat\", merge_agent={merge_agent})"

        elif ex_type == "FallbackExpr":
            primary_code = self._resolve_expression(expr["primary"])
            backup_code = self._resolve_expression(expr["backup"])
            return f"nexa_fallback(lambda: {primary_code}, lambda: {backup_code})"
        elif ex_type == "ImgCall":
            path = expr["path"]
            return f"nexa_img_loader('{path}')"

        # ===== P2-2: Structured Concurrency 表达式解析 =====
        elif ex_type == "SpawnExpression":
            handler_str = self._resolve_expression(expr.get("handler", {"type": "Identifier", "value": "None"}))
            return f"spawn({handler_str})"
        elif ex_type == "ParallelExpression":
            handlers_str = self._resolve_expression(expr.get("handlers", {"type": "Identifier", "value": "[]"}))
            return f"parallel({handlers_str})"
        elif ex_type == "RaceExpression":
            handlers_str = self._resolve_expression(expr.get("handlers", {"type": "Identifier", "value": "[]"}))
            return f"race({handlers_str})"
        elif ex_type == "ChannelDeclaration":
            return "channel()"
        elif ex_type == "AfterExpression":
            delay_str = self._resolve_expression(expr.get("delay", {"type": "Identifier", "value": "0"}))
            handler_str = self._resolve_expression(expr.get("handler", {"type": "Identifier", "value": "None"}))
            return f"after({delay_str}, {handler_str})"
        elif ex_type == "ScheduleExpression":
            interval_str = self._resolve_expression(expr.get("interval", {"type": "Identifier", "value": "0"}))
            handler_str = self._resolve_expression(expr.get("handler", {"type": "Identifier", "value": "None"}))
            return f"schedule({interval_str}, {handler_str})"
        elif ex_type == "SelectExpression":
            channels_str = self._resolve_expression(expr.get("channels", {"type": "Identifier", "value": "[]"}))
            timeout_str = ""
            if expr.get("timeout"):
                timeout_str = f", {self._resolve_expression(expr['timeout'])}"
            return f"select({channels_str}{timeout_str})"

        # ===== P3-4: ADT — Variant Call Expression =====
        elif ex_type == "VariantCallExpression":
            enum_name = expr.get('enum_name', '')
            variant_name = expr.get('variant_name', '')
            arguments = expr.get('arguments', [])
            args_strs = [self._resolve_expression(a) for a in arguments]
            args_str = ', '.join(args_strs)
            return f"make_variant('{enum_name}', '{variant_name}', {args_str})"
        
        elif ex_type == "FieldInitExpression":
            key = expr.get('key', '')
            value = expr.get('value', {})
            if value:
                value_str = self._resolve_expression(value)
            else:
                value_str = 'None'
            return f"{key}={value_str}"

        # ===== P3-6: Null Coalescing Expression (空值合并) =====
        elif ex_type == "NullCoalesceExpression":
            parts = expr.get("parts", [])
            if not parts:
                return "None"
            # Generate nested _nexa_null_coalesce calls: a ?? b ?? c => _nexa_null_coalesce(_nexa_null_coalesce(a, b), c)
            result = self._resolve_expression(parts[0])
            for part in parts[1:]:
                right_str = self._resolve_expression(part)
                result = f"_nexa_null_coalesce({result}, {right_str})"
            return result

        return "None"

    # ===== v1.2: Error Propagation — 辅助代码生成方法 =====

    def _resolve_try_op_expression(self, expr):
        """解析 ? 操作符的表达式,生成 propagate_or_else() 调用
        
        ? 操作符的核心:对表达式结果执行 unwrap
        - 如果 expr 是 Agent.run() -> 改为 Agent.run_result() 以获取 NexaResult
        - 如果 expr 是普通表达式 -> 使用 wrap_agent_result() 包装后 propagate_or_else
        
        生成代码: propagate_or_else(expr_str)
        其中 expr_str 可能包含 .run_result() 调用
        
        Args:
            expr: AST 表达式节点
        
        Returns:
            Python 代码字符串
        """
        expr_str = self._resolve_expression(expr)
        # 如果表达式包含 Agent.run(),改为 .run_result() 以获取 NexaResult
        expr_str = self._agent_run_to_run_result(expr_str)
        return f"propagate_or_else({expr_str})"

    def _agent_run_to_run_result(self, expr_str):
        """将 Agent.run() 调用转换为 Agent.run_result() 调用
        
        这是 ? 操作符和 otherwise 的关键:
        - Agent.run() 返回字符串(向后兼容)
        - Agent.run_result() 返回 NexaResult(支持 ? 和 otherwise)
        
        当 ? 或 otherwise 作用于 Agent 调用时,
        需要使用 run_result() 来获取 NexaResult 包装.
        
        Args:
            expr_str: 可能包含 .run() 的 Python 代码字符串
        
        Returns:
            替换 .run() 为 .run_result() 的 Python 代码字符串
        """
        # 检测 Agent.run() 调用模式:
        # - "AgentName.run(args)" -> "AgentName.run_result(args)"
        # - "expr >> AgentName.run(args)" 需要更复杂的处理
        import re
        # 匹配: IDENTIFIER.run( 但不匹配 NexaResult.run_result()
        # 使用负向断言避免匹配 .run_result()
        pattern = r'\.run\((?!_result)'
        result = re.sub(pattern, '.run_result(', expr_str)
        return result

    def _resolve_otherwise_handler(self, handler):
        """解析 otherwise handler 并生成对应的 Python 代码
        
        otherwise handler 可以是:
        - OtherwiseAgentHandler -> Agent.run_result() 作为 fallback
        - OtherwiseValueHandler -> 字符串/值作为默认值
        - OtherwiseVarHandler -> 变量引用作为默认值
        - OtherwiseBlockHandler -> 代码块(lambda)
        
        Args:
            handler: AST otherwise handler 节点
        
        Returns:
            Python 代码字符串
        """
        if not isinstance(handler, dict):
            # 简单值处理
            return repr(handler)
        
        handler_type = handler.get("type", "")
        
        if handler_type == "OtherwiseAgentHandler":
            # Agent fallback: 生成 Agent.run_result() 调用
            agent_call = handler.get("agent_call")
            if isinstance(agent_call, dict):
                agent_call_str = self._resolve_expression(agent_call)
                # 将 .run() 改为 .run_result()
                agent_call_str = self._agent_run_to_run_result(agent_call_str)
                return agent_call_str
            # 如果是字符串形式的 Agent 名称
            return str(agent_call)
        
        elif handler_type == "OtherwiseValueHandler":
            # 值 fallback: 直接返回值
            value = handler.get("value", "")
            return repr(value)
        
        elif handler_type == "OtherwiseVarHandler":
            # 变量 fallback: 直接返回变量名
            variable = handler.get("variable", "")
            return variable
        
        elif handler_type == "OtherwiseBlockHandler":
            # 代码块 fallback: 生成 lambda 表达式
            statements = handler.get("statements", [])
            if not statements:
                return repr("")
            # 生成代码块中的语句
            # 用 lambda 封装,lambda 接收 error 参数
            block_lines = []
            for stmt in statements:
                stmt_str = self._generate_inline_statement(stmt)
                block_lines.append(stmt_str)
            # 如果最后一个语句是表达式,作为 fallback 的返回值
            if block_lines:
                # 将多条语句封装在 lambda 中
                # 使用 (expr1, expr2, ..., fallback_value) 形式
                lambda_body = ", ".join(block_lines)
                return f"lambda __err: ({lambda_body})"
            return repr("")
        
        # 默认: 未知 handler 类型,返回字符串值
        return repr(handler.get("value", str(handler)))

    def _generate_inline_statement(self, stmt):
        """生成单行语句代码(用于 otherwise block handler 中)
        
        Args:
            stmt: AST 语句节点
        
        Returns:
            Python 代码字符串(单行)
        """
        st_type = stmt.get("type")
        if st_type == "ExpressionStatement":
            return self._resolve_expression(stmt["expression"])
        elif st_type == "AssignmentStatement":
            target = stmt["target"]
            val_str = self._resolve_expression(stmt["value"])
            return f"{target} = {val_str}"
        elif st_type == "PrintStatement":
            # print() 在 lambda 中返回 None
            val_str = self._resolve_expression(stmt.get("expression", stmt))
            return f"print({val_str})"
        # 简单表达式
        elif st_type in ("StringLiteral", "InterpolatedString", "Identifier", "IntLiteral", "FloatLiteral",
                         "BooleanLiteral", "MethodCallExpression", "FunctionCallExpression"):
            return self._resolve_expression(stmt)
        return str(stmt)

if __name__ == "__main__":
    import sys
    from src.nexa_parser import parse
    from src.ast_transformer import NexaTransformer
    
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        src = f.read()
    
    tree = parse(src)
    transformer = NexaTransformer()
    ast = transformer.transform(tree)
    
    generator = CodeGenerator(ast)
    print(generator.generate())
