# 此文件由 Nexa v0.5 Code Generator 自动生成
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

class WeatherReport(pydantic.BaseModel):
    city: str
    temperature: str
    conditions: str
    forecast: str

# Type: Register protocol "WeatherReport" fields in type checker
__type_checker.register_protocol_field("WeatherReport", "city", AliasTypeExpr("Any"))
__type_checker.register_protocol_field("WeatherReport", "temperature", AliasTypeExpr("Any"))
__type_checker.register_protocol_field("WeatherReport", "conditions", AliasTypeExpr("Any"))
__type_checker.register_protocol_field("WeatherReport", "forecast", AliasTypeExpr("Any"))

__tool_WeatherAPI_schema = {
    "name": "WeatherAPI",
    "description": "Fetch weather data for a city",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {"type": "string"}
        },
        "required": ["city"]
    }
}

# @implements: feature.weather_bot
WeatherBot = NexaAgent(
    name="WeatherBot",
    prompt="Provide weather information for cities. When asked about weather, include temperature, conditions, and forecast.",
    model="minimax-m2.5",
    role="Weather Assistant",
    memory_scope="local",
    stream=False,
    cache=False,
    protocol=WeatherReport,
    timeout=30,
    retry=3,
    tools=[__tool_WeatherAPI_schema]
)

def flow_main():
    result = WeatherBot.run("What is the weather in Beijing?")
    print(result)

if __name__ == "__main__":
    flow_main()
