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

from .agent import NexaAgent
from .result_types import NexaResult, NexaOption, ErrorPropagation, propagate_or_else, try_propagate, wrap_agent_result
from .evaluator import nexa_semantic_eval, nexa_intent_routing
from .orchestrator import join_agents, nexa_pipeline
from .memory import global_memory
from .dag_orchestrator import dag_fanout, dag_merge, dag_branch, dag_parallel_map, SmartRouter
from .cache_manager import NexaCacheManager
from .compactor import ContextCompactor
from .long_term_memory import LongTermMemory
from .knowledge_graph import KnowledgeGraph
from .memory_backend import SQLiteMemoryBackend, InMemoryBackend, VectorMemoryBackend
from .rbac import RBACManager, Role, Permission, SecurityContext
from .opencli import OpenCLI, NexaCLI
from .contracts import ContractSpec, ContractClause, OldValues, ContractViolation, check_requires, check_ensures, check_invariants, capture_old_values
from .inspector import inspect_nexa_file, infer_dag_topology, format_inspect_json, format_inspect_text
from .validator import validate_nexa_file, ValidationError, format_error_json, format_error_human
# v1.1: 渐进式类型系统 (Gradual Type System)
from .type_system import (
    TypeMode, LintMode, get_type_mode, get_lint_mode,
    TypeExpr, PrimitiveTypeExpr, GenericTypeExpr, UnionTypeExpr, OptionTypeExpr,
    ResultTypeExpr, AliasTypeExpr, FuncTypeExpr, SemanticTypeExpr, InferredType,
    TypeInferrer, TypeChecker, TypeViolation, TypeWarning, TypeCheckResult,
    TypeNarrower, build_type_expr_from_ast, build_protocol_fields_from_ast, check_type, check_protocol,
)
from .config import load_nexa_config, find_nexa_toml, get_config_value, create_default_nexa_toml
# P1-4: Built-In HTTP Server (内置HTTP服务器)
from .http_server import (
    RouteSegment, RouteSegmentType, Route, RouteMatchResult, RouteMatch,
    parse_route_pattern, match_route,
    CorsConfig, CspConfig, SecurityConfig, NexaRequest, NexaResponse,
    ServerState, NexaHttpServer, ContractViolation,
    HotReloadWatcher, parse_server_block, format_routes_text, format_routes_json,
    text, html, json_response, redirect, status_response, create_response,
    parse_form, parse_json_body, create_error_response,
    get_mime_type, cache_control_for, find_static_file, serve_static_file,
    apply_security_headers, get_default_security_headers,
)
# P1-5: Database Integration (内置数据库集成)
from .database import (
    NexaDatabase, NexaSQLite, NexaPostgres, DatabaseError,
    query, query_one, execute, close, begin, commit, rollback,
    python_to_sql, sql_to_python, adapt_sql_params,
    agent_memory_query, agent_memory_store, agent_memory_delete, agent_memory_list,
    contract_violation_to_http_status, verify_wal_mode, verify_foreign_keys,
    get_active_connections,
)
# P2-1: Built-In Auth & OAuth (内置认证与 OAuth)
from .auth import (
    NexaAuth, ProviderConfig, AuthConfig, Session,
    oauth, enable_auth, get_user, get_session,
    jwt_sign, jwt_verify, jwt_decode,
    csrf_token, csrf_field, verify_csrf,
    require_auth, require_auth_middleware, logout_user,
    agent_api_key_generate, agent_api_key_verify,
    agent_auth_context,
)
# P2-3: KV Store (内置键值存储)
from .kv_store import (
    NexaKVStore, KVHandle,
    kv_open, kv_get, kv_get_int, kv_get_str, kv_get_json,
    kv_set, kv_set_nx, kv_del, kv_has, kv_list,
    kv_expire, kv_ttl, kv_flush, kv_incr,
    agent_kv_query, agent_kv_store, agent_kv_context,
    serialize_value, deserialize_value,
    get_active_kv_stores,
)
# P2-2: Structured Concurrency (结构化并发)
from .concurrent import (
    NexaChannel, NexaTask, NexaSchedule, NexaConcurrencyRuntime, RUNTIME,
    channel, send, recv, recv_timeout, try_recv, close,
    select, spawn, await_task, try_await, cancel_task,
    parallel, race, after, schedule, cancel_schedule,
    sleep_ms, thread_count, parse_interval,
    get_active_channels, get_active_tasks, get_active_schedules, shutdown_runtime,
)
# P2-4: Template System (模板系统)
from .template import (
    NexaTemplateRenderer, TemplateContentParser,
    _nexa_tpl_escape, _nexa_tpl_join, _nexa_tpl_safe_str,
    FILTER_REGISTRY, apply_filter_chain,
    render_string, template, compile_template, render,
    agent_template_prompt, agent_template_slot_fill,
    agent_template_register, agent_template_list, agent_template_unregister,
    get_active_templates, CompiledTemplate,
    filter_upper, filter_uppercase, filter_lower, filter_lowercase,
    filter_capitalize, filter_trim, filter_truncate, filter_replace,
    filter_escape, filter_raw, filter_safe, filter_default,
    filter_length, filter_first, filter_last, filter_reverse,
    filter_join, filter_slice, filter_json, filter_number,
    filter_url_encode, filter_strip_tags, filter_word_count,
    filter_line_count, filter_indent, filter_date,
    filter_sort, filter_unique, filter_abs, filter_ceil, filter_floor,
)

# P3-6: Null Coalescing helper (空值合并辅助函数)
def _nexa_null_coalesce(left, right):
    if left is None:
        return right
    if isinstance(left, dict) and left.get('_nexa_option_variant') == 'None':
        return right
    if isinstance(left, dict) and not left:
        return right
    return left

# P3-5: Defer helper (延迟执行辅助函数)
def _nexa_defer_execute(stack):
    while stack:
        try:
            stack.pop()()
        except Exception:
            pass

# P3-3: Pattern Matching
from src.runtime.pattern_matching import (
    nexa_match_pattern,
    nexa_destructure,
    nexa_make_variant,
    _nexa_is_tuple_like,
    _nexa_is_list_like,
    _nexa_is_dict_with_keys,
    _nexa_is_variant,
    _nexa_list_rest,
    _nexa_dict_rest,
)
# P3-4: ADT — Struct/Enum/Trait/Impl (代数数据类型)
from src.runtime.adt import (
    register_struct, make_struct_instance, struct_get_field, struct_set_field,
    is_struct_instance, lookup_struct, get_all_structs,
    register_enum, make_variant, make_unit_variant, is_variant_instance,
    lookup_enum, get_all_enums,
    register_trait, register_impl, call_trait_method,
    lookup_trait, lookup_impl, get_all_traits, get_all_impls,
    adt_reset_registries, adt_get_registry_summary,
)

# P3-1: String Interpolation helper (字符串插值辅助函数)
def _nexa_interp_str(value):
    'Convert any value to string for interpolation. None -> empty string, dict -> JSON, etc.'
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
            import json as _json
            return _json.dumps(value, default=str)
        except Exception:
            return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        try:
            import json as _json
            return _json.dumps(value, default=str)
        except Exception:
            return str(value)
    return str(value)

__all__ = [
    # Core
    "NexaAgent", "nexa_semantic_eval", "nexa_intent_routing",
    # P3-5/P3-6/P3-1: Defer, Null Coalescing, String Interpolation helpers
    "_nexa_null_coalesce", "_nexa_defer_execute", "_nexa_interp_str",
    "nexa_match_pattern", "nexa_destructure", "nexa_make_variant",
    "_nexa_is_tuple_like", "_nexa_is_list_like", "_nexa_is_dict_with_keys", "_nexa_is_variant", "_nexa_list_rest", "_nexa_dict_rest",
    # P3-4: ADT — Struct/Enum/Trait/Impl
    "register_struct", "make_struct_instance", "struct_get_field", "struct_set_field",
    "is_struct_instance", "lookup_struct", "get_all_structs",
    "register_enum", "make_variant", "make_unit_variant", "is_variant_instance",
    "lookup_enum", "get_all_enums",
    "register_trait", "register_impl", "call_trait_method",
    "lookup_trait", "lookup_impl", "get_all_traits", "get_all_impls",
    "adt_reset_registries", "adt_get_registry_summary",
    # v1.2: Error Propagation (错误传播)
    "NexaResult", "NexaOption", "ErrorPropagation",
    "propagate_or_else", "try_propagate", "wrap_agent_result",
    "join_agents", "nexa_pipeline", "global_memory",
    # DAG Orchestrator
    "dag_fanout", "dag_merge", "dag_branch", "dag_parallel_map", "SmartRouter",
    # Cache & Compaction
    "NexaCacheManager", "ContextCompactor",
    # Memory Systems
    "LongTermMemory", "KnowledgeGraph",
    "SQLiteMemoryBackend", "InMemoryBackend", "VectorMemoryBackend",
    # Security
    "RBACManager", "Role", "Permission", "SecurityContext",
    # CLI
    "OpenCLI", "NexaCLI",
    # Contracts (Design by Contract)
    "ContractSpec", "ContractClause", "OldValues", "ContractViolation",
    "check_requires", "check_ensures", "check_invariants", "capture_old_values",
    # Inspector & Validator (Agent-Native Tooling)
    "inspect_nexa_file", "infer_dag_topology", "format_inspect_json", "format_inspect_text",
    "validate_nexa_file", "ValidationError", "format_error_json", "format_error_human",
    # v1.1: Gradual Type System (渐进式类型系统)
    "TypeMode", "LintMode", "get_type_mode", "get_lint_mode",
    "TypeExpr", "PrimitiveTypeExpr", "GenericTypeExpr", "UnionTypeExpr", "OptionTypeExpr",
    "ResultTypeExpr", "AliasTypeExpr", "FuncTypeExpr", "SemanticTypeExpr", "InferredType",
    "TypeInferrer", "TypeChecker", "TypeViolation", "TypeWarning", "TypeCheckResult",
    "TypeNarrower", "build_type_expr_from_ast", "build_protocol_fields_from_ast",
    "check_type", "check_protocol",
    # v1.1: Configuration (nexa.toml)
    "load_nexa_config", "find_nexa_toml", "get_config_value", "create_default_nexa_toml",
    # P1-4: Built-In HTTP Server (内置HTTP服务器)
    "RouteSegment", "RouteSegmentType", "Route", "RouteMatchResult", "RouteMatch",
    "parse_route_pattern", "match_route",
    "CorsConfig", "CspConfig", "SecurityConfig", "NexaRequest", "NexaResponse",
    "ServerState", "NexaHttpServer", "ContractViolation",
    "HotReloadWatcher", "parse_server_block", "format_routes_text", "format_routes_json",
    "text", "html", "json_response", "redirect", "status_response", "create_response",
    "parse_form", "parse_json_body", "create_error_response",
    "get_mime_type", "cache_control_for", "find_static_file", "serve_static_file",
    "apply_security_headers", "get_default_security_headers",
    # P1-5: Database Integration (内置数据库集成)
    "NexaDatabase", "NexaSQLite", "NexaPostgres", "DatabaseError",
    "query", "query_one", "execute", "close", "begin", "commit", "rollback",
    "python_to_sql", "sql_to_python", "adapt_sql_params",
    "agent_memory_query", "agent_memory_store", "agent_memory_delete", "agent_memory_list",
    "contract_violation_to_http_status", "verify_wal_mode", "verify_foreign_keys",
    "get_active_connections",
    # P2-1: Built-In Auth & OAuth (内置认证与 OAuth)
    "NexaAuth", "ProviderConfig", "AuthConfig", "Session",
    "oauth", "enable_auth", "get_user", "get_session",
    "jwt_sign", "jwt_verify", "jwt_decode",
    "csrf_token", "csrf_field", "verify_csrf",
    "require_auth", "logout_user",
    "agent_api_key_generate", "agent_api_key_verify",
    "agent_auth_context",
    "require_auth_middleware",
    # P2-3: KV Store (内置键值存储)
    "NexaKVStore", "KVHandle",
    "kv_open", "kv_get", "kv_get_int", "kv_get_str", "kv_get_json",
    "kv_set", "kv_set_nx", "kv_del", "kv_has", "kv_list",
    "kv_expire", "kv_ttl", "kv_flush", "kv_incr",
    "agent_kv_query", "agent_kv_store", "agent_kv_context",
    "serialize_value", "deserialize_value",
    "get_active_kv_stores",
    # P2-2: Structured Concurrency (结构化并发)
    "NexaChannel", "NexaTask", "NexaSchedule", "NexaConcurrencyRuntime", "RUNTIME",
    "channel", "send", "recv", "recv_timeout", "try_recv", "close",
    "select", "spawn", "await_task", "try_await", "cancel_task",
    "parallel", "race", "after", "schedule", "cancel_schedule",
    "sleep_ms", "thread_count", "parse_interval",
    "get_active_channels", "get_active_tasks", "get_active_schedules", "shutdown_runtime",
    # P2-4: Template System (模板系统)
    "NexaTemplateRenderer", "TemplateContentParser",
    "_nexa_tpl_escape", "_nexa_tpl_join", "_nexa_tpl_safe_str",
    "FILTER_REGISTRY", "apply_filter_chain",
    "render_string", "template", "compile_template", "render",
    "agent_template_prompt", "agent_template_slot_fill",
    "agent_template_register", "agent_template_list", "agent_template_unregister",
    "get_active_templates", "CompiledTemplate",
    "filter_upper", "filter_uppercase", "filter_lower", "filter_lowercase",
    "filter_capitalize", "filter_trim", "filter_truncate", "filter_replace",
    "filter_escape", "filter_raw", "filter_safe", "filter_default",
    "filter_length", "filter_first", "filter_last", "filter_reverse",
    "filter_join", "filter_slice", "filter_json", "filter_number",
    "filter_url_encode", "filter_strip_tags", "filter_word_count",
    "filter_line_count", "filter_indent", "filter_date",
    "filter_sort", "filter_unique", "filter_abs", "filter_ceil", "filter_floor",
]
