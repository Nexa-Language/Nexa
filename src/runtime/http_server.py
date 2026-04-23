"""
P1-4: Built-In HTTP Server — Nexa Agent-Native HTTP 服务器运行时

从 NTNT 的 http_server.rs / http_server_async.rs / http_bridge.rs 深度学习，
以 Nexa Agent-Native 方式差异化实现。

核心差异化:
- Agent 即 Handler: route GET "/chat" => ChatBot
- 语义路由: LLM 意图匹配请求到最适合的 Agent
- DAG pipeline 路由: route POST "/analyze" => Extractor |>> Analyzer |>> Reporter
- 契约联动: requires→400, ensures→500
"""

import os
import re
import uuid
import time
import json
import html as _html_stdlib
import mimetypes
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
from urllib.parse import urlparse, parse_qs, unquote


# =============================================================================
# 路由模式解析与匹配 (学习自 NTNT RouteSegment / Route / RouteMatchResult)
# =============================================================================

class RouteSegmentType(Enum):
    """路由段类型: 静态文本 / 参数 / 类型约束参数"""
    STATIC = "static"
    PARAM = "param"
    TYPED_PARAM = "typed_param"


@dataclass
class RouteSegment:
    """路由段 — 对应 NTNT RouteSegment"""
    seg_type: RouteSegmentType
    value: str  # 静态文本值 or 参数名
    param_type: Optional[str] = None  # 类型约束: "int", "float", None(=str)


@dataclass
class Route:
    """路由定义 — 对应 NTNT Route"""
    method: str  # GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
    pattern: str  # 原始模式字符串 "/users/{id}"
    segments: List[RouteSegment] = field(default_factory=list)
    handler_name: str = ""  # handler 函数名 / Agent名
    handler_type: str = "fn"  # "fn" | "agent" | "dag" | "semantic"
    dag_chain: List[str] = field(default_factory=list)  # DAG handler链


class RouteMatchResult(Enum):
    """路由匹配三态结果 — 对应 NTNT RouteMatchResult"""
    MATCHED = "matched"
    TYPE_MISMATCH = "type_mismatch"
    NOT_FOUND = "not_found"


@dataclass
class RouteMatch:
    """路由匹配详细信息"""
    result: RouteMatchResult
    handler_name: str = ""
    params: Dict[str, str] = field(default_factory=dict)
    route: Optional[Route] = None
    type_mismatch_param: str = ""
    type_mismatch_expected: str = ""
    type_mismatch_got: str = ""


def parse_route_pattern(pattern: str) -> List[RouteSegment]:
    """
    解析路由模式为段列表 — 学习自 NTNT parse_route_pattern
    
    支持:
    - 静态段: /users, /api
    - 参数段: {id}, {name}
    - 类型约束参数段: {id: int}, {price: float}
    
    Examples:
        "/" → []
        "/users" → [Static("users")]
        "/users/{id}" → [Static("users"), Param("id")]
        "/users/{id: int}" → [Static("users"), TypedParam("id", "int")]
    """
    if pattern == "/":
        return []
    
    # 移除前导 /
    path = pattern.lstrip("/")
    parts = path.split("/")
    segments = []
    
    for part in parts:
        if not part:
            continue
        
        # 检查参数模式 {name} 或 {name: type}
        param_match = re.match(r'^\{(\w+)(?:\s*:\s*(\w+))?\}$', part)
        if param_match:
            name = param_match.group(1)
            type_constraint = param_match.group(2)
            if type_constraint:
                segments.append(RouteSegment(
                    seg_type=RouteSegmentType.TYPED_PARAM,
                    value=name,
                    param_type=type_constraint.lower()
                ))
            else:
                segments.append(RouteSegment(
                    seg_type=RouteSegmentType.PARAM,
                    value=name
                ))
        else:
            segments.append(RouteSegment(
                seg_type=RouteSegmentType.STATIC,
                value=part
            ))
    
    return segments


def match_route(path: str, route: Route) -> RouteMatch:
    """
    匹配请求路径到路由 — 学习自 NTNT match_route
    
    返回三态结果:
    - MATCHED: 路径匹配成功，包含提取的参数
    - TYPE_MISMATCH: 模式匹配但类型约束失败
    - NOT_FOUND: 路径不匹配
    
    HEAD 请求自动回退到 GET 路由 (RFC 9110 §9.3.2)
    """
    method = route.method
    
    # HEAD 回退到 GET
    if method == "HEAD":
        # 不做 HEAD→GET 回退，让专门注册的 HEAD 路由优先
        pass
    
    # 处理根路径
    if path == "/" and not route.segments:
        return RouteMatch(result=RouteMatchResult.MATCHED, handler_name=route.handler_name, route=route)
    
    # 分割请求路径
    path_parts = [p for p in path.lstrip("/").split("/") if p]
    
    # 段数量必须匹配
    if len(path_parts) != len(route.segments):
        return RouteMatch(result=RouteMatchResult.NOT_FOUND)
    
    params = {}
    for path_part, segment in zip(path_parts, route.segments):
        if segment.seg_type == RouteSegmentType.STATIC:
            if path_part != segment.value:
                return RouteMatch(result=RouteMatchResult.NOT_FOUND)
        elif segment.seg_type == RouteSegmentType.PARAM:
            params[segment.value] = path_part
        elif segment.seg_type == RouteSegmentType.TYPED_PARAM:
            # 类型约束验证
            if segment.param_type == "int":
                try:
                    int(path_part)
                    params[segment.value] = path_part
                except ValueError:
                    return RouteMatch(
                        result=RouteMatchResult.TYPE_MISMATCH,
                        type_mismatch_param=segment.value,
                        type_mismatch_expected="int",
                        type_mismatch_got=path_part,
                        route=route
                    )
            elif segment.param_type == "float":
                try:
                    float(path_part)
                    params[segment.value] = path_part
                except ValueError:
                    return RouteMatch(
                        result=RouteMatchResult.TYPE_MISMATCH,
                        type_mismatch_param=segment.value,
                        type_mismatch_expected="float",
                        type_mismatch_got=path_part,
                        route=route
                    )
            else:
                # 未知类型约束，默认接受
                params[segment.value] = path_part
    
    return RouteMatch(
        result=RouteMatchResult.MATCHED,
        handler_name=route.handler_name,
        params=params,
        route=route
    )


# =============================================================================
# CORS 配置 (学习自 NTNT CorsConfig)
# =============================================================================

@dataclass
class CorsConfig:
    """CORS 配置 — 对应 NTNT CorsConfig"""
    origins: List[str] = field(default_factory=lambda: ["*"])
    methods: List[str] = field(default_factory=lambda: [
        "GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"
    ])
    headers: List[str] = field(default_factory=lambda: [
        "Content-Type", "Authorization", "Accept"
    ])
    credentials: bool = False
    max_age: int = 86400
    
    def is_origin_allowed(self, origin: str) -> bool:
        """检查来源是否允许"""
        if "*" in self.origins:
            return True
        return origin in self.origins
    
    def get_allow_origin(self, request_origin: Optional[str] = None) -> Optional[str]:
        """获取 Access-Control-Allow-Origin 响应值"""
        if request_origin and self.is_origin_allowed(request_origin):
            if self.credentials:
                return request_origin
            elif "*" in self.origins:
                return "*"
            else:
                return request_origin
        elif not self.credentials and "*" in self.origins:
            return "*"
        return None
    
    def apply_to_response(self, response: Dict[str, Any], request_origin: Optional[str] = None) -> None:
        """将 CORS headers 应用到响应"""
        headers = response.get("headers", {})
        if not isinstance(headers, dict):
            headers = {}
        
        allow_origin = self.get_allow_origin(request_origin)
        if allow_origin:
            headers["access-control-allow-origin"] = allow_origin
        headers["access-control-allow-methods"] = ", ".join(self.methods)
        headers["access-control-allow-headers"] = ", ".join(self.headers)
        if self.credentials:
            headers["access-control-allow-credentials"] = "true"
        headers["access-control-max-age"] = str(self.max_age)
        
        response["headers"] = headers
    
    def create_preflight_response(self, request_origin: Optional[str] = None) -> Dict[str, Any]:
        """创建 preflight (OPTIONS) 响应"""
        headers = {}
        allow_origin = self.get_allow_origin(request_origin)
        if allow_origin:
            headers["access-control-allow-origin"] = allow_origin
        headers["access-control-allow-methods"] = ", ".join(self.methods)
        headers["access-control-allow-headers"] = ", ".join(self.headers)
        if self.credentials:
            headers["access-control-allow-credentials"] = "true"
        headers["access-control-max-age"] = str(self.max_age)
        return create_response(204, headers, "")
    
    @classmethod
    def from_dict(cls, options: Dict[str, Any]) -> 'CorsConfig':
        """从字典创建 CORS 配置"""
        config = cls()
        if "origins" in options:
            origins = options["origins"]
            if isinstance(origins, str):
                config.origins = [origins]
            elif isinstance(origins, list):
                config.origins = origins
        if "methods" in options:
            methods = options["methods"]
            if isinstance(methods, list):
                config.methods = [m.upper() for m in methods]
        if "headers" in options:
            hdrs = options["headers"]
            if isinstance(hdrs, list):
                config.headers = hdrs
        if "credentials" in options:
            config.credentials = bool(options["credentials"])
        if "max_age" in options:
            config.max_age = int(options["max_age"])
        return config


# =============================================================================
# CSP 配置 (学习自 NTNT CspConfig)
# =============================================================================

@dataclass
class CspConfig:
    """CSP 配置 — 对应 NTNT CspConfig"""
    directives: Dict[str, str] = field(default_factory=lambda: {
        "default-src": "'self'",
        "script-src": "'self'",
        "style-src": "'self' 'unsafe-inline'",
        "img-src": "'self' data: https:",
        "font-src": "'self'",
        "connect-src": "'self'",
        "frame-ancestors": "'none'",
        "base-uri": "'self'",
        "form-action": "'self'",
    })
    report_only: bool = False
    
    def to_header_value(self) -> str:
        """构建 CSP header 值字符串"""
        parts = [f"{k} {v}" for k, v in sorted(self.directives.items())]
        return "; ".join(parts)
    
    def header_name(self) -> str:
        """获取 header 名称 (report-only 或 enforcing)"""
        if self.report_only:
            return "content-security-policy-report-only"
        return "content-security-policy"
    
    def apply_to_response(self, response: Dict[str, Any]) -> None:
        """将 CSP header 应用到响应"""
        headers = response.get("headers", {})
        if not isinstance(headers, dict):
            headers = {}
        key = self.header_name()
        # 不覆盖已设置的 CSP
        if key not in headers and key.lower() not in {k.lower() for k in headers}:
            headers[key] = self.to_header_value()
        response["headers"] = headers
    
    @classmethod
    def from_dict(cls, options: Dict[str, Any]) -> 'CspConfig':
        """从字典创建 CSP 配置"""
        config = cls()
        if "report_only" in options:
            config.report_only = bool(options["report_only"])
        # 其他字符串键都是 CSP 指令
        for key, value in options.items():
            if key == "report_only":
                continue
            if isinstance(value, str):
                config.directives[key] = value
        return config


# =============================================================================
# 安全配置 (学习自 NTNT SecurityConfig)
# =============================================================================

def _parse_size(s: str) -> Optional[int]:
    """解析大小字符串如 "10MB", "1GB" → 字节数"""
    s = s.strip().upper()
    if s.endswith("GB"):
        num = s[:-2].strip()
        try:
            return int(num) * 1024 * 1024 * 1024
        except ValueError:
            return None
    elif s.endswith("MB"):
        num = s[:-2].strip()
        try:
            return int(num) * 1024 * 1024
        except ValueError:
            return None
    elif s.endswith("KB"):
        num = s[:-2].strip()
        try:
            return int(num) * 1024
        except ValueError:
            return None
    elif s.endswith("B"):
        num = s[:-1].strip()
        try:
            return int(num)
        except ValueError:
            return None
    else:
        try:
            return int(s)
        except ValueError:
            return None


@dataclass
class SecurityConfig:
    """安全配置 — 对应 NTNT SecurityConfig"""
    max_body_size: int = 10 * 1024 * 1024  # 10MB
    security_headers: bool = True
    production_mode: bool = False
    detailed_errors: bool = True  # 开发模式默认详细
    
    @classmethod
    def from_env(cls) -> 'SecurityConfig':
        """从环境变量加载配置"""
        production = os.environ.get("NEXA_ENV", "").lower() in ("production", "prod")
        max_body = os.environ.get("NEXA_MAX_BODY_SIZE", "10MB")
        parsed_body = _parse_size(max_body)
        
        sec_headers = os.environ.get("NEXA_SECURITY_HEADERS", "true").lower() not in ("0", "false")
        detailed = os.environ.get("NEXA_DETAILED_ERRORS", "").lower() in ("1", "true") if os.environ.get("NEXA_DETAILED_ERRORS") else not production
        
        return cls(
            max_body_size=parsed_body or 10 * 1024 * 1024,
            security_headers=sec_headers,
            production_mode=production,
            detailed_errors=detailed,
        )


def get_default_security_headers() -> Dict[str, str]:
    """
    默认安全响应头 — 对应 NTNT get_default_security_headers
    
    防止常见 Web 漏洞:
    - MIME 类型嗅探 (X-Content-Type-Options)
    - 点击劫持 (X-Frame-Options)
    - 引用泄露 (Referrer-Policy)
    - XSS (X-XSS-Protection)
    - HSTS (生产模式)
    - 权限策略 (Permissions-Policy)
    """
    headers = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "x-xss-protection": "1; mode=block",
        "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
    }
    
    # HSTS: 生产模式强制 HTTPS
    production = os.environ.get("NEXA_ENV", "").lower() in ("production", "prod")
    if production:
        headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
    
    return headers


def apply_security_headers(response: Dict[str, Any]) -> None:
    """
    应用安全头到响应 — 对应 NTNT apply_security_headers
    
    已存在的 header 不被覆盖（应用可自定义）
    """
    config = SecurityConfig.from_env()
    headers = response.get("headers", {})
    if not isinstance(headers, dict):
        headers = {}
    
    if config.security_headers:
        sec_headers = get_default_security_headers()
        for key, value in sec_headers.items():
            # 不覆盖已设置的 header（大小写不敏感比较）
            existing_lower = {k.lower() for k in headers}
            if key.lower() not in existing_lower:
                headers[key] = value
    
    # Cache-Control: 动态响应默认 no-store
    has_cache_control = any(k.lower() == "cache-control" for k in headers)
    if not has_cache_control:
        headers["cache-control"] = "no-store"
    
    response["headers"] = headers


# =============================================================================
# 请求与响应对象 (学习自 NTNT BridgeRequest / BridgeResponse)
# =============================================================================

@dataclass
class NexaRequest:
    """
    Nexa HTTP 请求对象 — 对应 NTNT BridgeRequest
    
    Agent-Native 扩展:
    - context: 中间件可注入的上下文（如认证用户、特征标志）
    """
    method: str
    path: str
    url: str
    query: str
    query_params: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, str] = field(default_factory=dict)  # 路径参数
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""
    id: str = ""
    ip: str = "unknown"
    protocol: str = "http"
    context: Dict[str, Any] = field(default_factory=dict)  # 中间件注入
    
    @classmethod
    def from_raw(cls, method: str, path: str, headers: Dict[str, str] = None,
                 body: str = "", query_string: str = "",
                 client_ip: str = "unknown", protocol: str = "http") -> 'NexaRequest':
        """从原始 HTTP 请求构造 NexaRequest"""
        # 解析查询参数
        query_params = {}
        if query_string:
            for key, values in parse_qs(query_string).items():
                query_params[key] = values[0] if len(values) == 1 else ",".join(values)
        
        # 构造完整 URL
        url = path
        if query_string:
            url = f"{path}?{query_string}"
        
        # 请求 ID
        req_id = headers.get("x-request-id", str(uuid.uuid4())[:8]) if headers else str(uuid.uuid4())[:8]
        
        return cls(
            method=method.upper(),
            path=path,
            url=url,
            query=query_string,
            query_params=query_params,
            headers=headers or {},
            body=body,
            id=req_id,
            ip=client_ip,
            protocol=protocol,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（供 Agent 输入）"""
        return {
            "method": self.method,
            "path": self.path,
            "url": self.url,
            "query": self.query,
            "query_params": self.query_params,
            "params": self.params,
            "headers": self.headers,
            "body": self.body,
            "id": self.id,
            "ip": self.ip,
            "protocol": self.protocol,
            "context": self.context,
        }


@dataclass
class NexaResponse:
    """Nexa HTTP 响应对象"""
    status: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "status": self.status,
            "headers": self.headers,
            "body": self.body,
        }


# =============================================================================
# 响应辅助函数 (学习自 NTNT text/html/json/redirect/status)
# =============================================================================

def text(content: str, status: int = 200) -> Dict[str, Any]:
    """创建纯文本响应"""
    return {"status": status, "headers": {"content-type": "text/plain; charset=utf-8"}, "body": content}


def html(content: str, status: int = 200) -> Dict[str, Any]:
    """创建 HTML 响应"""
    return {"status": status, "headers": {"content-type": "text/html; charset=utf-8"}, "body": content}


def json_response(data: Any, status: int = 200) -> Dict[str, Any]:
    """创建 JSON 响应"""
    body = json.dumps(data, ensure_ascii=False, default=str)
    return {"status": status, "headers": {"content-type": "application/json; charset=utf-8"}, "body": body}


def redirect(url: str, status: int = 302) -> Dict[str, Any]:
    """创建重定向响应"""
    return {"status": status, "headers": {"location": url}, "body": ""}


def status_response(code: int, message: str = "") -> Dict[str, Any]:
    """创建仅状态码响应"""
    return {"status": code, "headers": {}, "body": message}


def create_response(status: int, headers: Dict[str, str], body: str) -> Dict[str, Any]:
    """创建完整响应"""
    return {"status": status, "headers": headers, "body": body}


def parse_form(req: NexaRequest) -> Dict[str, str]:
    """解析表单请求体 (application/x-www-form-urlencoded)"""
    params = {}
    if req.body:
        for key, values in parse_qs(req.body).items():
            params[key] = values[0] if len(values) == 1 else ",".join(values)
    return params


def parse_json_body(req: NexaRequest) -> Optional[Any]:
    """解析 JSON 请求体"""
    if not req.body:
        return None
    try:
        return json.loads(req.body)
    except (json.JSONDecodeError, ValueError):
        return None


# =============================================================================
# 错误响应 (学习自 NTNT create_error_response)
# =============================================================================

def _html_escape(s: str) -> str:
    """HTML escape using stdlib"""
    return _html_stdlib.escape(s, quote=True)


def create_error_response(status: int, message: str, is_production: bool = False) -> Dict[str, Any]:
    """
    创建错误响应 — 对应 NTNT create_error_response
    
    开发模式: 详细 HTML 错误页面
    生产模式: 精简安全错误页面
    
    契约错误自动映射:
    - requires 失败 → 400 Bad Request
    - ensures 失败 → 500 Internal Server Error
    """
    status_texts = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error",
        503: "Service Unavailable",
    }
    status_text = status_texts.get(status, "Error")
    
    if is_production:
        # 生产模式: 精简
        body = f"<h1>{status} {status_text}</h1>"
    else:
        # 开发模式: 详细
        body = f"""<!DOCTYPE html>
<html><head><title>{status} {status_text}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; }}
h1 {{ color: #dc2626; font-size: 24px; margin-bottom: 16px; }}
.detail {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px; margin: 8px 0; }}
.label {{ font-weight: 600; color: #991b1b; }}
.value {{ color: #1c1917; }}
</style></head>
<body>
<h1>{status} {status_text}</h1>
<div class="detail"><span class="label">Error</span><span class="value">{_html_escape(message)}</span></div>
</body></html>"""
    
    return {
        "status": status,
        "headers": {"content-type": "text/html; charset=utf-8", "server": "nexa-http"},
        "body": body,
    }


# =============================================================================
# 静态文件服务 (学习自 NTNT serve_static + MIME + Cache-Control)
# =============================================================================

# MIME 类型映射
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".webm": "video/webm",
}


def get_mime_type(filename: str) -> str:
    """获取文件的 MIME 类型"""
    ext = os.path.splitext(filename)[1].lower()
    return MIME_TYPES.get(ext, "application/octet-stream")


def cache_control_for(filename: str) -> str:
    """
    分级缓存策略 — 学习自 NTNT cache_control_for
    
    - 图片/字体: public, max-age=31536000, immutable (1年)
    - CSS/JS: public, max-age=86400 (1天)
    - HTML: no-cache (每次验证)
    - 其他: public, max-age=3600 (1小时)
    """
    ext = os.path.splitext(filename)[1].lower()
    
    immutable_extensions = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
                           ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mp3", ".wav", ".webm"}
    daily_extensions = {".css", ".js"}
    no_cache_extensions = {".html"}
    
    if ext in immutable_extensions:
        return "public, max-age=31536000, immutable"
    elif ext in daily_extensions:
        return "public, max-age=86400"
    elif ext in no_cache_extensions:
        return "no-cache"
    else:
        return "public, max-age=3600"


def find_static_file(path: str, static_dirs: List[Tuple[str, str]]) -> Optional[Tuple[str, str]]:
    """
    查找静态文件 — 学习自 NTNT ServerState.find_static_file
    
    static_dirs: [(url_prefix, filesystem_path), ...]
    返回: (filesystem_path, url_prefix) or None
    
    安全: 阻止路径遍历攻击
    """
    for url_prefix, fs_path in static_dirs:
        if not path.startswith(url_prefix):
            continue
        
        # 计算相对路径
        relative = path[len(url_prefix):].lstrip("/")
        
        # 安全: 阻止路径遍历
        if ".." in relative or relative.startswith("/"):
            continue
        
        full_path = os.path.join(fs_path, relative)
        
        # 确保不超出基础目录
        real_base = os.path.realpath(fs_path)
        real_path = os.path.realpath(full_path)
        if not real_path.startswith(real_base):
            continue
        
        if os.path.isfile(real_path):
            return (real_path, url_prefix)
    
    return None


def serve_static_file(filepath: str) -> Dict[str, Any]:
    """读取静态文件并创建响应"""
    try:
        with open(filepath, "rb") as f:
            content = f.read()
        
        mime = get_mime_type(filepath)
        cc = cache_control_for(filepath)
        
        # 二进制文件 → base64 或原始 bytes
        # 对于文本文件，解码为 str
        if mime.startswith("text/") or mime.startswith("application/json") or mime.startswith("application/javascript"):
            body = content.decode("utf-8", errors="replace")
        else:
            # 二进制内容用 base64 标记（实际 HTTP 服务器会直接发送 bytes）
            import base64
            body = base64.b64encode(content).decode("ascii")
        
        return {
            "status": 200,
            "headers": {
                "content-type": mime,
                "cache-control": cc,
                "server": "nexa-http",
            },
            "body": body,
            "_binary": not mime.startswith("text/") and not mime.startswith("application/json") and not mime.startswith("application/javascript"),
        }
    except (IOError, OSError):
        return create_error_response(404, f"File not found: {filepath}")


# =============================================================================
# 服务器状态 (学习自 NTNT ServerState)
# =============================================================================

@dataclass
class ServerState:
    """
    服务器状态 — 对应 NTNT ServerState
    
    Agent-Native 扩展:
    - semantic_routes: 语义路由映射
    - agent_registry: Agent handler 注册表
    """
    routes: List[Route] = field(default_factory=list)
    static_dirs: List[Tuple[str, str]] = field(default_factory=list)  # (url_prefix, filesystem_path)
    middleware: List[Callable] = field(default_factory=list)
    cors_config: Optional[CorsConfig] = None
    csp_config: Optional[CspConfig] = None
    security_config: SecurityConfig = field(default_factory=SecurityConfig.from_env)
    error_handler: Optional[Callable] = None
    shutdown_handlers: List[Callable] = field(default_factory=list)
    hot_reload: bool = True
    
    # 路由索引: (method, segment_count) → route indices (O(1)查找优化)
    _route_index: Dict[Tuple[str, int], List[int]] = field(default_factory=dict)
    
    # Nexa Agent-Native 特色
    agent_registry: Dict[str, Any] = field(default_factory=dict)  # name → agent instance
    semantic_routes: List[Route] = field(default_factory=list)  # 语义路由
    
    def add_route(self, method: str, pattern: str, handler_name: str,
                  handler_type: str = "fn", dag_chain: List[str] = None) -> Route:
        """注册路由"""
        route = Route(
            method=method.upper(),
            pattern=pattern,
            segments=parse_route_pattern(pattern),
            handler_name=handler_name,
            handler_type=handler_type,
            dag_chain=dag_chain or [],
        )
        self.routes.append(route)
        
        # 更新索引
        seg_count = len(route.segments)
        key = (method.upper(), seg_count)
        if key not in self._route_index:
            self._route_index[key] = []
        self._route_index[key].append(len(self.routes) - 1)
        
        return route
    
    def add_semantic_route(self, pattern: str, handler_name: str) -> Route:
        """注册语义路由 — Nexa 特色"""
        route = Route(
            method="SEMANTIC",
            pattern=pattern,
            segments=parse_route_pattern(pattern),
            handler_name=handler_name,
            handler_type="semantic",
        )
        self.semantic_routes.append(route)
        return route
    
    def add_static_dir(self, url_prefix: str, filesystem_path: str) -> None:
        """注册静态文件目录"""
        self.static_dirs.append((url_prefix, filesystem_path))
    
    def add_middleware(self, handler: Callable) -> None:
        """注册中间件"""
        self.middleware.append(handler)
    
    def add_shutdown_handler(self, handler: Callable) -> None:
        """注册关机处理器"""
        self.shutdown_handlers.append(handler)
    
    def register_agent(self, name: str, agent_instance: Any) -> None:
        """注册 Agent 实例"""
        self.agent_registry[name] = agent_instance
    
    def find_route(self, method: str, path: str) -> RouteMatch:
        """
        查找匹配路由 — 学习自 NTNT ServerState.find_route
        
        HEAD → GET 回退 (RFC 9110 §9.3.2)
        类型约束验证
        """
        method_upper = method.upper()
        
        # 优先匹配显式 HEAD 路由
        if method_upper == "HEAD":
            # 先找显式 HEAD 路由
            match = self._find_route_exact("HEAD", path)
            if match.result == RouteMatchResult.MATCHED:
                return match
            # 回退到 GET 路由
            match = self._find_route_exact("GET", path)
            return match
        
        return self._find_route_exact(method_upper, path)
    
    def _find_route_exact(self, method: str, path: str) -> RouteMatch:
        """精确方法查找路由"""
        path_parts = [p for p in path.lstrip("/").split("/") if p]
        seg_count = len(path_parts)
        
        # 使用索引加速查找
        key = (method, seg_count)
        candidate_indices = self._route_index.get(key, [])
        
        # 根路径特殊处理
        if path == "/":
            key = (method, 0)
            candidate_indices = self._route_index.get(key, [])
        
        for idx in candidate_indices:
            route = self.routes[idx]
            match = match_route(path, route)
            if match.result == RouteMatchResult.MATCHED:
                return match
            elif match.result == RouteMatchResult.TYPE_MISMATCH:
                return match
        
        # 索引未命中 → 全量搜索（防止漏配）
        for route in self.routes:
            if route.method == method:
                match = match_route(path, route)
                if match.result in (RouteMatchResult.MATCHED, RouteMatchResult.TYPE_MISMATCH):
                    return match
        
        return RouteMatch(result=RouteMatchResult.NOT_FOUND)
    
    def route_count(self) -> int:
        """路由数量"""
        return len(self.routes)
    
    def static_dir_count(self) -> int:
        """静态目录数量"""
        return len(self.static_dirs)
    
    def clear(self) -> None:
        """清除所有状态（hot-reload 用）"""
        self.routes.clear()
        self._route_index.clear()
        self.static_dirs.clear()
        self.middleware.clear()
        self.shutdown_handlers.clear()
        self.semantic_routes.clear()
    
    def clear_routes_and_middleware(self) -> None:
        """清除路由和中间件，保留静态目录和关机处理器（hot-reload 用）"""
        self.routes.clear()
        self._route_index.clear()
        self.middleware.clear()
        self.semantic_routes.clear()


# =============================================================================
# Nexa HTTP 服务器 (学习自 NTNT async server architecture)
# =============================================================================

class NexaHttpServer:
    """
    Nexa Agent-Native HTTP 服务器
    
    Python runtime 使用 aiohttp 异步服务器（Agent 需要异步 LLM 调用）
    
    Agent-Native 特色:
    - Agent 直接作为路由 handler: agent.run(req.body) → response
    - DAG pipeline 作为路由: 多 Agent 串联
    - 语义路由: LLM 意图匹配
    - 契约联动: requires→400, ensures→500
    
    中间件链:
    middleware_fn(req) → 修改后的 NexaRequest or None(拒绝)
    """
    
    def __init__(self, port: int = 8080, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self.state = ServerState()
        self._running = False
    
    def route(self, method: str, pattern: str, handler_name: str,
              handler_type: str = "fn", dag_chain: List[str] = None) -> Route:
        """注册路由"""
        return self.state.add_route(method, pattern, handler_name, handler_type, dag_chain)
    
    def semantic_route(self, pattern: str, handler_name: str) -> Route:
        """注册语义路由"""
        return self.state.add_semantic_route(pattern, handler_name)
    
    def static(self, url_prefix: str, filesystem_path: str) -> None:
        """注册静态文件目录"""
        self.state.add_static_dir(url_prefix, filesystem_path)
    
    def use_middleware(self, handler: Callable) -> None:
        """注册中间件"""
        self.state.add_middleware(handler)
    
    def cors(self, config: Union[CorsConfig, Dict[str, Any]]) -> None:
        """配置 CORS"""
        if isinstance(config, dict):
            self.state.cors_config = CorsConfig.from_dict(config)
        else:
            self.state.cors_config = config
    
    def csp(self, config: Union[CspConfig, Dict[str, Any]]) -> None:
        """配置 CSP"""
        if isinstance(config, dict):
            self.state.csp_config = CspConfig.from_dict(config)
        else:
            self.state.csp_config = config
    
    def on_shutdown(self, handler: Callable) -> None:
        """注册关机处理器"""
        self.state.add_shutdown_handler(handler)
    
    def register_agent(self, name: str, agent: Any) -> None:
        """注册 Agent 实例"""
        self.state.register_agent(name, agent)
    
    def error_handler(self, handler: Callable) -> None:
        """注册全局错误处理器"""
        self.state.error_handler = handler
    
    def handle_request(self, method: str, path: str,
                       headers: Dict[str, str] = None,
                       body: str = "", query_string: str = "",
                       client_ip: str = "unknown",
                       protocol: str = "http",
                       handler_map: Dict[str, Callable] = None,
                       agent_map: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理 HTTP 请求 — 核心请求处理流程
        
        handler_map: 函数名 → handler Callable
        agent_map: Agent名 → Agent instance (优先使用 state.agent_registry)
        
        流程:
        1. 构造 NexaRequest
        2. 运行中间件链
        3. 路由匹配
        4. Handler 执行 (fn/agent/dag/semantic)
        5. 应用 CORS/CSP/Security headers
        6. 返回响应
        
        HEAD 请求: 保留状态和 headers，移除 body (RFC 9110 §9.3.2)
        OPTIONS 请求: CORS preflight 自动响应
        """
        # 构造请求
        req = NexaRequest.from_raw(
            method=method, path=path, headers=headers or {},
            body=body, query_string=query_string,
            client_ip=client_ip, protocol=protocol
        )
        
        # OPTIONS: CORS preflight
        if method.upper() == "OPTIONS" and self.state.cors_config:
            origin = headers.get("origin", None) if headers else None
            return self.state.cors_config.create_preflight_response(origin)
        
        # 1. 运行中间件链
        for mw in self.state.middleware:
            result = mw(req)
            if result is None:
                # 中间件拒绝请求
                return create_error_response(403, "Forbidden: middleware rejection",
                                           self.state.security_config.production_mode)
            req = result  # 中间件修改后的请求
        
        # 2. 路由匹配
        match = self.state.find_route(method, path)
        
        if match.result == RouteMatchResult.TYPE_MISMATCH:
            # 类型约束失败 → 400
            msg = f"Type mismatch: parameter '{match.type_mismatch_param}' expected {match.type_mismatch_expected}, got '{match.type_mismatch_got}'"
            return create_error_response(400, msg, self.state.security_config.production_mode)
        
        if match.result == RouteMatchResult.NOT_FOUND:
            # 查找静态文件
            static_result = find_static_file(path, self.state.static_dirs)
            if static_result:
                filepath, _ = static_result
                response = serve_static_file(filepath)
                apply_security_headers(response)
                return response
            
            # 语义路由匹配 (Nexa 特色)
            if self.state.semantic_routes and body:
                semantic_match = self._match_semantic_route(path, body, agent_map)
                if semantic_match:
                    response = semantic_match
                    apply_security_headers(response)
                    if self.state.cors_config:
                        origin = headers.get("origin", None) if headers else None
                        self.state.cors_config.apply_to_response(response, origin)
                    return response
            
            # 404
            return create_error_response(404, f"Not Found: {method} {path}",
                                        self.state.security_config.production_mode)
        
        # 3. 提取路径参数到请求
        req.params = match.params
        
        # 4. Handler 执行
        route = match.route
        try:
            response = self._execute_handler(route, req, handler_map, agent_map)
        except ContractViolation as e:
            # 契约违反映射
            if e.contract_type == "requires":
                return create_error_response(400, f"Bad Request: {e.message}",
                                           self.state.security_config.production_mode)
            else:
                return create_error_response(500, f"Internal Error: {e.message}",
                                           self.state.security_config.production_mode)
        except Exception as e:
            # 全局错误处理器
            if self.state.error_handler:
                try:
                    response = self.state.error_handler(req, e)
                    if isinstance(response, dict):
                        return response
                except Exception:
                    pass
            return create_error_response(500, str(e),
                                        self.state.security_config.production_mode)
        
        # 5. HEAD 请求: 移除 body (RFC 9110 §9.3.2)
        if method.upper() == "HEAD":
            response["body"] = ""
        
        # 6. 应用 CORS/CSP/Security headers
        if isinstance(response, dict):
            apply_security_headers(response)
            if self.state.cors_config:
                origin = headers.get("origin", None) if headers else None
                self.state.cors_config.apply_to_response(response, origin)
            if self.state.csp_config:
                self.state.csp_config.apply_to_response(response)
            response.setdefault("headers", {})["server"] = "nexa-http"
        
        return response
    
    def _execute_handler(self, route: Route, req: NexaRequest,
                         handler_map: Dict[str, Callable] = None,
                         agent_map: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行路由 handler
        
        handler_type:
        - "fn": 查找 handler_map 中的函数并调用
        - "agent": 查找 agent_map/registry 中的 Agent 并 run
        - "dag": 执行 DAG pipeline
        - "semantic": LLM 语义匹配
        """
        effective_agents = agent_map or self.state.agent_registry
        effective_handlers = handler_map or {}
        
        if route.handler_type == "agent":
            # Agent handler: agent.run(req.body or req.to_dict())
            agent = effective_agents.get(route.handler_name)
            if agent is None:
                return create_error_response(500, f"Agent not found: {route.handler_name}",
                                           self.state.security_config.production_mode)
            
            # 将请求转换为 Agent 输入
            agent_input = req.body or req.to_dict()
            result = agent.run(agent_input)
            
            # Agent 返回字符串 → text response
            if isinstance(result, str):
                return text(result)
            # Agent 返回 dict → json response
            elif isinstance(result, dict):
                return json_response(result)
            else:
                return text(str(result))
        
        elif route.handler_type == "dag":
            # DAG pipeline handler: 串联多个 Agent
            dag_chain = route.dag_chain
            current_input = req.body or req.to_dict()
            
            for agent_name in dag_chain:
                agent = effective_agents.get(agent_name)
                if agent is None:
                    return create_error_response(500, f"Agent not found in DAG: {agent_name}",
                                               self.state.security_config.production_mode)
                current_input = agent.run(current_input)
            
            if isinstance(current_input, str):
                return text(current_input)
            elif isinstance(current_input, dict):
                return json_response(current_input)
            else:
                return text(str(current_input))
        
        elif route.handler_type == "semantic":
            # 语义路由: 使用 nexa_semantic_eval 匹配意图
            from .evaluator import nexa_semantic_eval
            agent = effective_agents.get(route.handler_name)
            if agent is None:
                return create_error_response(500, f"Agent not found: {route.handler_name}",
                                           self.state.security_config.production_mode)
            
            # 语义评估请求意图
            intent = nexa_semantic_eval(f"What is the intent of this HTTP request: {req.method} {req.path} with body: {req.body[:200]}")
            result = agent.run(req.body or intent)
            
            if isinstance(result, str):
                return text(result)
            elif isinstance(result, dict):
                return json_response(result)
            else:
                return text(str(result))
        
        else:  # "fn"
            # 函数 handler
            handler_fn = effective_handlers.get(route.handler_name)
            if handler_fn is None:
                return create_error_response(500, f"Handler not found: {route.handler_name}",
                                           self.state.security_config.production_mode)
            
            # 调用 handler 函数
            result = handler_fn(req)
            
            # handler 返回 dict → 直接作为响应
            if isinstance(result, dict):
                if "status" in result:
                    return result
                else:
                    return json_response(result)
            elif isinstance(result, str):
                # 简单字符串 → text response
                return text(result)
            else:
                return text(str(result))
    
    def _match_semantic_route(self, path: str, body: str,
                              agent_map: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        语义路由匹配 — Nexa Agent-Native 特色
        
        当精确路由未匹配时，尝试用 LLM 语义匹配请求意图到最适合的语义路由 Agent
        """
        if not self.state.semantic_routes:
            return None
        
        try:
            from .evaluator import nexa_semantic_eval
            
            # 构造意图描述
            intent_desc = f"HTTP request to {path} with content: {body[:500]}"
            
            # 评估最适合的语义路由
            best_match = None
            best_score = 0
            
            for route in self.state.semantic_routes:
                # 每个语义路由的 Agent 名和路径模式
                match_desc = f"Route {route.pattern} handled by {route.handler_name}"
                score = nexa_semantic_eval(f"How well does '{match_desc}' match intent '{intent_desc}'? Rate 0-10.")
                
                try:
                    score_val = float(str(score).strip())
                except (ValueError, TypeError):
                    score_val = 0
                
                if score_val > best_score and score_val >= 5:
                    best_score = score_val
                    best_match = route
            
            if best_match and best_score >= 5:
                # 执行最佳语义路由的 Agent
                effective_agents = agent_map or self.state.agent_registry
                agent = effective_agents.get(best_match.handler_name)
                if agent:
                    result = agent.run(body)
                    if isinstance(result, str):
                        return text(result)
                    elif isinstance(result, dict):
                        return json_response(result)
                    else:
                        return text(str(result))
        except Exception:
            pass
        
        return None
    
    def serve(self) -> None:
        """启动 HTTP 服务器（同步模式，用于测试）"""
        self._running = True
        print(f"🚀 Nexa HTTP Server starting on http://{self.host}:{self.port}")
        print(f"   Routes: {self.state.route_count()}  |  Static: {self.state.static_dir_count()}  |  Hot-reload: {self.state.hot_reload}")
        # 实际服务器需要 aiohttp，这里只标记为运行状态
        # 真正的异步启动由生成的 Python 代码中的 asyncio.run() 执行
    
    def stop(self) -> None:
        """停止服务器"""
        self._running = False
        for handler in self.state.shutdown_handlers:
            try:
                handler()
            except Exception:
                pass
        print("🛑 Nexa HTTP Server stopped")


# =============================================================================
# ContractViolation for HTTP error mapping
# =============================================================================

class ContractViolation(Exception):
    """契约违反异常 — HTTP 错误映射用"""
    def __init__(self, message: str, contract_type: str = "requires"):
        super().__init__(message)
        self.message = message
        self.contract_type = contract_type  # "requires" → 400, "ensures"/"invariant" → 500


# =============================================================================
# Hot-Reload 支持 (学习自 NTNT hot-reload architecture)
# =============================================================================

class HotReloadWatcher:
    """
    文件变更检测器 — 学习自 NTNT hot-reload
    
    检测 .nx 源文件变更 → 触发服务器重载
    使用简单的 mtime 检测（不依赖 watchdog）
    """
    
    def __init__(self, file_paths: List[str]):
        self.file_paths = file_paths
        self._mtimes: Dict[str, float] = {}
        self._initialize()
    
    def _initialize(self) -> None:
        """记录初始 mtime"""
        for path in self.file_paths:
            try:
                self._mtimes[path] = os.path.getmtime(path)
            except OSError:
                self._mtimes[path] = 0
    
    def check_changes(self) -> List[str]:
        """检查变更，返回已变更文件列表"""
        changed = []
        for path in self.file_paths:
            try:
                current_mtime = os.path.getmtime(path)
                if current_mtime != self._mtimes.get(path, 0):
                    changed.append(path)
                    self._mtimes[path] = current_mtime
            except OSError:
                pass
        return changed
    
    def add_file(self, path: str) -> None:
        """添加监视文件"""
        if path not in self.file_paths:
            self.file_paths.append(path)
            try:
                self._mtimes[path] = os.path.getmtime(path)
            except OSError:
                self._mtimes[path] = 0


# =============================================================================
# Server Block DSL 解析辅助 (供 code_generator 使用)
# =============================================================================

def parse_server_block(ast_node: Dict[str, Any]) -> NexaHttpServer:
    """
    从 AST ServerDeclaration 构造 NexaHttpServer
    
    AST 格式:
    {
        "type": "ServerDeclaration",
        "port": 8080,
        "directives": [...],
        "routes": [...],
        "groups": [...]
    }
    """
    server = NexaHttpServer(port=ast_node.get("port", 8080))
    
    # 处理指令
    for directive in ast_node.get("directives", []):
        if directive["type"] == "ServerStatic" or directive["type"] == "server_static":
            server.static(directive["url_prefix"], directive["filesystem_path"])
        elif directive["type"] == "ServerCors" or directive["type"] == "server_cors":
            server.cors(directive.get("config", {}))
        elif directive["type"] == "ServerMiddleware" or directive["type"] == "server_middleware":
            # 中间件名在运行时解析
            pass
    
    # 处理路由
    for route_node in ast_node.get("routes", []):
        handler_type = route_node.get("handler_type", "fn")
        dag_chain = route_node.get("dag_chain", [])
        server.route(
            method=route_node["method"],
            pattern=route_node["pattern"],
            handler_name=route_node["handler"],
            handler_type=handler_type,
            dag_chain=dag_chain,
        )
    
    # 处理组
    for group in ast_node.get("groups", []):
        prefix = group.get("prefix", "")
        for route_node in group.get("routes", []):
            full_pattern = f"{prefix}{route_node['pattern']}"
            server.route(
                method=route_node["method"],
                pattern=full_pattern,
                handler_name=route_node["handler"],
                handler_type=route_node.get("handler_type", "fn"),
                dag_chain=route_node.get("dag_chain", []),
            )
    
    return server


def format_routes_text(state: ServerState) -> str:
    """格式化路由列表为可读文本"""
    lines = []
    for route in state.routes:
        handler_info = route.handler_name
        if route.handler_type == "agent":
            handler_info = f"[Agent] {route.handler_name}"
        elif route.handler_type == "dag":
            handler_info = f"[DAG] {route.dag_chain[0]} |>> ... |>> {route.dag_chain[-1]}"
        elif route.handler_type == "semantic":
            handler_info = f"[Semantic] {route.handler_name}"
        lines.append(f"  {route.method:6s} {route.pattern:30s} → {handler_info}")
    
    for route in state.semantic_routes:
        lines.append(f"  SEM    {route.pattern:30s} → [Semantic] {route.handler_name}")
    
    if state.static_dirs:
        for prefix, path in state.static_dirs:
            lines.append(f"  STATIC {prefix:30s} → {path}")
    
    return "\n".join(lines)


def format_routes_json(state: ServerState) -> str:
    """格式化路由列表为 JSON"""
    routes = []
    for route in state.routes:
        route_info = {
            "method": route.method,
            "pattern": route.pattern,
            "handler": route.handler_name,
            "handler_type": route.handler_type,
        }
        if route.dag_chain:
            route_info["dag_chain"] = route.dag_chain
        routes.append(route_info)
    
    for route in state.semantic_routes:
        routes.append({
            "method": "SEMANTIC",
            "pattern": route.pattern,
            "handler": route.handler_name,
            "handler_type": "semantic",
        })
    
    static = []
    for prefix, path in state.static_dirs:
        static.append({"prefix": prefix, "path": path})
    
    return json.dumps({"routes": routes, "static": static}, indent=2)