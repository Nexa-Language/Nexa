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

'''
P2-1: Built-In Auth & OAuth — Nexa Agent-Native 认证运行时

核心差异化: Agent-Native 三层认证模型 (API Key + JWT + OAuth)
- Layer 1: API Key Auth — Agent-to-Agent / M2M 认证
- Layer 2: JWT Auth — 服务间认证
- Layer 3: OAuth Auth — 人类用户认证（与 HTTP Server 联动）

与已有模块联动:
- http_server.py: require_auth 在 NexaHttpServer.handle_request 中检查
- contracts.py: 401→ContractViolation requires, 403→ContractViolation ensures
- database.py: SQLiteSessionStore 使用 Nexa 已有的 sqlite3
'''

import os
import re
import uuid
import time
import json
import hmac
import hashlib
import base64
import secrets
import sqlite3
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable, Union

# 尝试导入 PyJWT（核心依赖）
try:
    import jwt as pyjwt
    HAS_PYJWT = True
except ImportError:
    HAS_PYJWT = False

# 尝试导入 requests（OAuth token exchange 依赖）
try:
    import requests as http_requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# =============================================================================
# 数据结构 (学习自 NTNT auth.rs config.rs)
# =============================================================================

@dataclass
class ProviderConfig:
    '''OAuth Provider 配置 — 对应 NTNT ProviderConfig'''
    name: str              # 'google', 'github', 'custom'
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: List[str] = field(default_factory=list)
    use_pkce: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'authorize_url': self.authorize_url,
            'token_url': self.token_url,
            'userinfo_url': self.userinfo_url,
            'scopes': self.scopes,
            'use_pkce': self.use_pkce,
        }


@dataclass
class AuthConfig:
    '''Auth 系统配置 — 对应 NTNT AuthConfig'''
    providers: List[ProviderConfig] = field(default_factory=list)
    session_secret: str = ''
    session_ttl: int = 3600           # 默认 1 小时
    cookie_name: str = 'nexa_session'
    cookie_secure: bool = False
    cookie_samesite: str = 'Lax'
    cookie_httponly: bool = True
    success_url: str = '/'
    failure_url: str = '/auth'
    logout_url: str = '/'
    protected_paths: List[str] = field(default_factory=list)
    session_store: str = 'memory'     # 'memory' | 'sqlite:PATH'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'providers': [p.to_dict() for p in self.providers],
            'session_secret': self.session_secret,
            'session_ttl': self.session_ttl,
            'cookie_name': self.cookie_name,
            'cookie_secure': self.cookie_secure,
            'success_url': self.success_url,
            'failure_url': self.failure_url,
            'logout_url': self.logout_url,
            'protected_paths': self.protected_paths,
            'session_store': self.session_store,
        }


@dataclass
class Session:
    '''用户会话 — 对应 NTNT Session'''
    id: str
    user_id: str = ''
    user_name: str = ''
    user_email: str = ''
    provider: str = ''
    csrf_token: str = ''
    access_token: str = ''
    refresh_token: str = ''
    expires_at: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: int = 0

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'user_email': self.user_email,
            'provider': self.provider,
            'csrf_token': self.csrf_token,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expires_at': self.expires_at,
            'data': self.data,
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Session':
        return cls(
            id=d.get('id', ''),
            user_id=d.get('user_id', ''),
            user_name=d.get('user_name', ''),
            user_email=d.get('user_email', ''),
            provider=d.get('provider', ''),
            csrf_token=d.get('csrf_token', ''),
            access_token=d.get('access_token', ''),
            refresh_token=d.get('refresh_token', ''),
            expires_at=d.get('expires_at', 0),
            data=d.get('data', {}),
            created_at=d.get('created_at', 0),
        )


@dataclass
class TokenResponse:
    '''OAuth Token 响应'''
    access_token: str = ''
    refresh_token: str = ''
    token_type: str = 'Bearer'
    expires_in: int = 3600
    id_token: str = ''
    scope: str = ''


# =============================================================================
# 内置 Provider 快捷方式 (学习自 NTNT providers.rs)
# =============================================================================

BUILTIN_PROVIDERS: Dict[str, ProviderConfig] = {
    'google': ProviderConfig(
        name='google',
        client_id='',
        client_secret='',
        authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
        token_url='https://oauth2.googleapis.com/token',
        userinfo_url='https://www.googleapis.com/oauth2/v2/userinfo',
        scopes=['openid', 'email', 'profile'],
        use_pkce=True,
    ),
    'github': ProviderConfig(
        name='github',
        client_id='',
        client_secret='',
        authorize_url='https://github.com/login/oauth/authorize',
        token_url='https://github.com/login/oauth/access_token',
        userinfo_url='https://api.github.com/user',
        scopes=['user:email'],
        use_pkce=False,
    ),
}


# =============================================================================
# 全局 Auth 状态
# =============================================================================

# 全局 AuthConfig 实例
_global_auth_config: Optional[AuthConfig] = None

# 全局 Session Store 实例
_global_session_store: Optional[Union['MemorySessionStore', 'SQLiteSessionStore']] = None

# Agent API Key 注册表
_api_key_registry: Dict[str, Dict[str, Any]] = {}


def _get_session_store() -> Union['MemorySessionStore', 'SQLiteSessionStore']:
    '''获取全局 Session Store'''
    if _global_session_store is None:
        if _global_auth_config is None:
            return MemorySessionStore()
        if _global_auth_config.session_store == 'memory':
            return MemorySessionStore()
        elif _global_auth_config.session_store.startswith('sqlite:'):
            path = _global_auth_config.session_store[7:]
            return SQLiteSessionStore(path)
        return MemorySessionStore()
    return _global_session_store


def _get_auth_config() -> AuthConfig:
    '''获取全局 AuthConfig'''
    if _global_auth_config is None:
        return AuthConfig()
    return _global_auth_config


# =============================================================================
# OAuth Provider 快捷方式与 Auth 初始化
# =============================================================================

def oauth(name: str, client_id: str, client_secret: str, opts: Dict[str, Any] = None) -> ProviderConfig:
    '''创建 OAuth Provider 配置 — 内置 google/github 快捷方式

    Args:
        name: Provider 名称 ('google', 'github', 或自定义)
        client_id: OAuth Client ID
        client_secret: OAuth Client Secret
        opts: 可选覆盖字段 (authorize_url, token_url, userinfo_url, scopes, use_pkce)

    Returns:
        ProviderConfig 实例
    '''
    opts = opts or {}

    # 检查内置 Provider
    if name in BUILTIN_PROVIDERS:
        base = BUILTIN_PROVIDERS[name]
        return ProviderConfig(
            name=name,
            client_id=client_id,
            client_secret=client_secret,
            authorize_url=opts.get('authorize_url', base.authorize_url),
            token_url=opts.get('token_url', base.token_url),
            userinfo_url=opts.get('userinfo_url', base.userinfo_url),
            scopes=opts.get('scopes', base.scopes),
            use_pkce=opts.get('use_pkce', base.use_pkce),
        )

    # 自定义 Provider — 必须提供 URL
    return ProviderConfig(
        name=name,
        client_id=client_id,
        client_secret=client_secret,
        authorize_url=opts.get('authorize_url', ''),
        token_url=opts.get('token_url', ''),
        userinfo_url=opts.get('userinfo_url', ''),
        scopes=opts.get('scopes', []),
        use_pkce=opts.get('use_pkce', False),
    )


def enable_auth(providers: List[ProviderConfig], options: Dict[str, Any] = None) -> AuthConfig:
    '''初始化 Auth 系统 — 对应 NTNT enable_auth

    Args:
        providers: OAuth Provider 列表
        options: 可选配置 (session_secret, session_ttl, cookie_name, etc.)

    Returns:
        AuthConfig 实例（同时设置为全局配置）
    '''
    options = options or {}

    # 自动生成 session_secret 如果未提供
    session_secret = options.get('session_secret', '')
    if not session_secret:
        session_secret = secrets.token_hex(32)

    config = AuthConfig(
        providers=providers,
        session_secret=session_secret,
        session_ttl=options.get('session_ttl', 3600),
        cookie_name=options.get('cookie_name', 'nexa_session'),
        cookie_secure=options.get('cookie_secure', False),
        cookie_samesite=options.get('cookie_samesite', 'Lax'),
        cookie_httponly=options.get('cookie_httponly', True),
        success_url=options.get('success_url', '/'),
        failure_url=options.get('failure_url', '/auth'),
        logout_url=options.get('logout_url', '/'),
        protected_paths=options.get('protected_paths', []),
        session_store=options.get('session_store', 'memory'),
    )

    # 设置为全局配置
    global _global_auth_config, _global_session_store
    _global_auth_config = config

    # 初始化 Session Store
    if config.session_store == 'memory':
        _global_session_store = MemorySessionStore()
    elif config.session_store.startswith('sqlite:'):
        path = config.session_store[7:]
        _global_session_store = SQLiteSessionStore(path)
    else:
        _global_session_store = MemorySessionStore()

    return config


# =============================================================================
# OAuth 流程 (学习自 NTNT oauth.rs)
# =============================================================================

def generate_auth_url(provider: ProviderConfig, redirect_uri: str,
                      state: str, nonce: str = None,
                      pkce: str = None) -> str:
    '''生成 OAuth Authorization URL

    Args:
        provider: OAuth Provider 配置
        redirect_uri: 回调 URL
        state: CSRF 状态参数
        nonce: OIDC nonce (可选)
        pkce: PKCE challenge (可选)

    Returns:
        完整的 authorization URL
    '''
    params = {
        'client_id': provider.client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(provider.scopes),
        'state': state,
    }

    if nonce:
        params['nonce'] = nonce

    if pkce:
        params['code_challenge'] = pkce
        params['code_challenge_method'] = 'S256'

    return f'{provider.authorize_url}?{urllib.parse.urlencode(params)}'


def exchange_code_for_tokens(provider: ProviderConfig, code: str,
                              redirect_uri: str,
                              pkce_verifier: str = None) -> TokenResponse:
    '''用 authorization code 交换 tokens — 对应 NTNT exchange_code_for_tokens

    使用 requests 库发送 token 请求

    Args:
        provider: OAuth Provider 配置
        code: Authorization code
        redirect_uri: 回调 URL
        pkce_verifier: PKCE verifier (可选)

    Returns:
        TokenResponse 实例
    '''
    if not HAS_REQUESTS:
        return TokenResponse()  # 无 requests 库时返回空响应

    data = {
        'client_id': provider.client_id,
        'client_secret': provider.client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }

    if pkce_verifier:
        data['code_verifier'] = pkce_verifier

    headers = {'Accept': 'application/json'}

    try:
        resp = http_requests.post(
            provider.token_url,
            data=data,
            headers=headers,
            timeout=30,
        )
        token_data = resp.json()

        return TokenResponse(
            access_token=token_data.get('access_token', ''),
            refresh_token=token_data.get('refresh_token', ''),
            token_type=token_data.get('token_type', 'Bearer'),
            expires_in=token_data.get('expires_in', 3600),
            id_token=token_data.get('id_token', ''),
            scope=token_data.get('scope', ''),
        )
    except Exception:
        return TokenResponse()


# =============================================================================
# PKCE (学习自 NTNT primitives.rs — S256 transformation)
# =============================================================================

def generate_pkce_verifier() -> str:
    '''生成 PKCE verifier — 43-128 随机字符 (学习自 NTNT)

    Returns:
        PKCE verifier 字符串
    '''
    # 43 字符 = 32 bytes hex (secrets.token_hex(32) = 64 chars)
    # 使用 43 字符以满足最小长度要求
    return secrets.token_urlsafe(32)[:43]


def generate_pkce_challenge(verifier: str) -> str:
    '''生成 PKCE challenge — SHA256 + Base64URL-no-pad (学习自 NTNT S256)

    Args:
        verifier: PKCE verifier 字符串

    Returns:
        PKCE challenge 字符串 (Base64URL 编码, 无 padding)
    '''
    digest = hashlib.sha256(verifier.encode('utf-8')).digest()
    # Base64URL 编码, 移除 padding
    b64 = base64.urlsafe_b64encode(digest).decode('utf-8')
    return b64.rstrip('=')


# =============================================================================
# JWT (学习自 NTNT jwt.rs — HS256 算法)
# =============================================================================

def jwt_sign(claims: Dict[str, Any], secret: str, options: Dict[str, Any] = None) -> str:
    '''JWT 签名 — HS256 算法 (学习自 NTNT)

    Args:
        claims: JWT claims 字典
        secret: 签名密钥
        options: 可选参数 (exp: 过期秒数, iat: 是否包含 issued-at)

    Returns:
        JWT token 字符串
    '''
    options = options or {}

    if not HAS_PYJWT:
        # 简易 JWT 实现（无 PyJWT 时的 fallback）
        import json as _json
        header = {'alg': 'HS256', 'typ': 'JWT'}
        # 添加 exp
        exp_seconds = options.get('exp', 0)
        if exp_seconds:
            claims['exp'] = int(time.time()) + exp_seconds
        # 添加 iat
        if options.get('iat', True):
            claims['iat'] = int(time.time())
        # 编码
        header_b64 = base64.urlsafe_b64encode(_json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(_json.dumps(claims).encode()).decode().rstrip('=')
        signing_input = f'{header_b64}.{payload_b64}'
        signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
        return f'{signing_input}.{sig_b64}'

    # 使用 PyJWT
    exp_seconds = options.get('exp', 0)
    if exp_seconds:
        claims['exp'] = int(time.time()) + exp_seconds
    if options.get('iat', True):
        claims['iat'] = int(time.time())

    return pyjwt.encode(claims, secret, algorithm='HS256')


def jwt_verify(token: str, secret: str) -> Optional[Dict[str, Any]]:
    '''JWT 验证 — HS256 算法 (学习自 NTNT)

    Args:
        token: JWT token 字符串
        secret: 签名密钥

    Returns:
        验证成功的 claims 字典, 或 None (验证失败)
    '''
    if not HAS_PYJWT:
        # 简易 JWT 验证（无 PyJWT 时的 fallback）
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None
            header_b64, payload_b64, sig_b64 = parts
            # 恢复 padding
            header_b64 += '=' * (4 - len(header_b64) % 4)
            payload_b64 += '=' * (4 - len(payload_b64) % 4)
            sig_b64 += '=' * (4 - len(sig_b64) % 4)
            # 验证签名
            signing_input = f'{parts[0]}.{parts[1]}'
            expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
            actual_sig = base64.urlsafe_b64decode(sig_b64)
            if not constant_time_compare(expected_sig, actual_sig):
                return None
            # 解码 payload
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            # 检查过期
            if 'exp' in payload and payload['exp'] < time.time():
                return None
            return payload
        except Exception:
            return None

    try:
        return pyjwt.decode(token, secret, algorithms=['HS256'])
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None


def jwt_decode(token: str) -> Dict[str, Any]:
    '''JWT 解码 — 不验签, 仅供调试 (学习自 NTNT)

    Args:
        token: JWT token 字符串

    Returns:
        claims 字典 (不验签)
    '''
    if not HAS_PYJWT:
        try:
            parts = token.split('.')
            if len(parts) < 2:
                return {}
            payload_b64 = parts[1]
            # 恢复 padding
            payload_b64 += '=' * (4 - len(payload_b64) % 4)
            return json.loads(base64.urlsafe_b64decode(payload_b64))
        except Exception:
            return {}

    try:
        return pyjwt.decode(token, options={'verify_signature': False}, algorithms=['HS256'])
    except Exception:
        return {}


# =============================================================================
# CSRF (学习自 NTNT — 双重提交 cookie + HMAC 签名)
# =============================================================================

def csrf_token(request: Any) -> str:
    '''生成 CSRF token — HMAC 签名 (学习自 NTNT)

    Token 缓存到 request._csrf_token 属性, 同一请求多次调用返回相同 token

    Args:
        request: NexaRequest 实例 (必须有 session)

    Returns:
        HMAC 签名的 CSRF token
    '''
    # 缓存: 同一请求返回相同 token
    if hasattr(request, '_csrf_token') and request._csrf_token:
        return request._csrf_token

    config = _get_auth_config()
    session = get_session(request)

    if session is None:
        # 无 session 时生成临时 token (缓存到 request)
        nonce = secrets.token_hex(16)
        token = hmac.new(
            config.session_secret.encode(),
            nonce.encode(),
            hashlib.sha256
        ).hexdigest()
    else:
        # 基于 session id 生成 HMAC 签名 token
        message = f'{session.id}:{session.csrf_token}'
        token = hmac.new(
            config.session_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    # 缓存到 request
    request._csrf_token = token
    return token


def csrf_field(request: Any) -> str:
    '''生成 HTML hidden input — CSRF 表单字段 (学习自 NTNT)

    Args:
        request: NexaRequest 实例

    Returns:
        HTML hidden input 字符串: <input type='hidden' name='_csrf' value='...'/>
    '''
    token = csrf_token(request)
    # 使用单引号避免 triple-quote 问题
    return f"<input type='hidden' name='_csrf' value='{token}'/>"


def verify_csrf(request: Any, token: str) -> bool:
    '''验证 CSRF token — 常量时间比较 (学习自 NTNT)

    Args:
        request: NexaRequest 实例
        token: 待验证的 CSRF token

    Returns:
        验证是否成功
    '''
    expected = csrf_token(request)
    return constant_time_compare(expected, token)


# =============================================================================
# HMAC Session Cookie (学习自 NTNT cookies.rs)
# =============================================================================

def sign_session_id(session_id: str, secret: str) -> str:
    '''签名 Session ID — HMAC-SHA256 (学习自 NTNT)

    Args:
        session_id: 原始 session ID
        secret: HMAC 签名密钥

    Returns:
        签名后的 token (格式: session_id.hmac_hex)
    '''
    sig = hmac.new(secret.encode(), session_id.encode(), hashlib.sha256).hexdigest()
    return f'{session_id}.{sig}'


def verify_session_id(signed_token: str, secret: str) -> Optional[str]:
    '''验证签名 Session ID — HMAC-SHA256 (学习自 NTNT)

    Args:
        signed_token: 签名后的 token
        secret: HMAC 签名密钥

    Returns:
        原始 session ID (验证成功), 或 None (验证失败)
    '''
    if '.' not in signed_token:
        return None

    # 从右分割一次（session_id 可能包含 .）
    parts = signed_token.rsplit('.', 1)
    if len(parts) != 2:
        return None

    session_id, sig = parts
    expected_sig = hmac.new(secret.encode(), session_id.encode(), hashlib.sha256).hexdigest()

    if constant_time_compare(expected_sig, sig):
        return session_id
    return None


def constant_time_compare(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
    '''常量时间比较 — 防止 timing attack (学习自 NTNT)

    Args:
        a: 第一个值
        b: 第二个值

    Returns:
        是否相等
    '''
    # 转换为 bytes
    if isinstance(a, str):
        a = a.encode()
    if isinstance(b, str):
        b = b.encode()

    if len(a) != len(b):
        return False

    result = 0
    for x, y in zip(a, b):
        result |= x ^ y

    return result == 0


# =============================================================================
# Session 管理 (学习自 NTNT sessions.rs)
# =============================================================================

def get_session(request: Any) -> Optional[Session]:
    '''从请求获取 Session — 对应 NTNT get_session

    Args:
        request: NexaRequest 实例 (必须有 cookies)

    Returns:
        Session 实例, 或 None (无有效 session)
    '''
    config = _get_auth_config()
    store = _get_session_store()

    # 从 cookie 获取签名 session ID
    cookie_name = config.cookie_name
    cookies = {}
    if hasattr(request, 'cookies'):
        cookies = request.cookies if isinstance(request.cookies, dict) else {}
    elif hasattr(request, 'headers'):
        cookie_header = request.headers.get('cookie', '')
        if isinstance(cookie_header, str):
            for part in cookie_header.split(';'):
                part = part.strip()
                if '=' in part:
                    k, v = part.split('=', 1)
                    cookies[k.strip()] = v.strip()

    signed_id = cookies.get(cookie_name, '')
    if not signed_id:
        return None

    # 验证签名
    session_id = verify_session_id(signed_id, config.session_secret)
    if session_id is None:
        return None

    # 从 store 获取 session
    session = store.get(session_id)
    if session is None:
        return None

    # 检查过期
    if session.is_expired():
        store.delete(session_id)
        return None

    return session


def get_user(request: Any) -> Optional[Dict[str, Any]]:
    '''获取当前用户信息 — 对应 NTNT get_user

    Args:
        request: NexaRequest 实例

    Returns:
        用户信息字典, 或 None (无有效 session)
    '''
    session = get_session(request)
    if session is None:
        return None

    return {
        'id': session.user_id,
        'name': session.user_name,
        'email': session.user_email,
        'provider': session.provider,
    }


def session_data(request: Any) -> Optional[Dict[str, Any]]:
    '''获取自定义会话数据 — 对应 NTNT session_data

    Args:
        request: NexaRequest 实例

    Returns:
        自定义数据字典, 或 None
    '''
    session = get_session(request)
    if session is None:
        return None
    return session.data


def set_session(request: Any, data: Dict[str, Any]) -> bool:
    '''设置自定义会话数据 — 对应 NTNT set_session

    Args:
        request: NexaRequest 实例
        data: 要设置的数据字典

    Returns:
        是否成功
    '''
    session = get_session(request)
    if session is None:
        return False

    session.data.update(data)
    store = _get_session_store()
    store.save(session)
    return True


def logout_user(request: Any) -> Dict[str, Any]:
    '''注销用户 — 对应 NTNT logout_user

    清除 session 并返回 redirect 响应

    Args:
        request: NexaRequest 实例

    Returns:
        redirect 响应字典
    '''
    config = _get_auth_config()
    store = _get_session_store()

    # 从 cookie 获取 session
    session = get_session(request)
    if session:
        store.delete(session.id)

    # 返回 redirect 响应 (清除 cookie + 重定向)
    return {
        'status': 302,
        'headers': {
            'location': config.logout_url,
            'set-cookie': f'{config.cookie_name}=; Path=/; Max-Age=0; HttpOnly; SameSite={config.cookie_samesite}',
        },
        'body': '',
    }


# =============================================================================
# require_auth 中间件 (学习自 NTNT guards.rs)
# =============================================================================

def require_auth(request: Any) -> Optional[Dict[str, Any]]:
    '''Auth 中间件 — 路径保护 (学习自 NTNT require_auth)

    与 ContractViolation 联动:
    - 401 → ContractViolation requires (未认证)
    - 403 → ContractViolation ensures (无权限)

    Args:
        request: NexaRequest 实例

    Returns:
        None (认证通过) 或 dict (拒绝响应)
    '''
    config = _get_auth_config()

    # 检查 API Key (Layer 1: Agent-to-Agent)
    api_key = None
    if hasattr(request, 'headers'):
        headers = request.headers if isinstance(request.headers, dict) else {}
        api_key = headers.get('authorization', '')
        if api_key.startswith('Bearer nexa-ak-'):
            api_key = api_key[7:]  # 移除 'Bearer ' 前缀
        elif api_key.startswith('nexa-ak-'):
            pass  # 直接使用
        else:
            api_key = headers.get('x-api-key', '')
            if not api_key.startswith('nexa-ak-'):
                api_key = ''

    if api_key and api_key.startswith('nexa-ak-'):
        # API Key 认证
        key_info = agent_api_key_verify(api_key)
        if key_info:
            # 认证通过 — 注入 auth context
            if hasattr(request, 'auth_context'):
                request.auth_context = key_info
            return None  # 通过

    # 检查 Session (Layer 3: OAuth)
    user = get_user(request)
    if user:
        # 认证通过
        return None

    # 检查 JWT (Layer 2: 服务间认证)
    if hasattr(request, 'headers'):
        headers = request.headers if isinstance(request.headers, dict) else {}
        auth_header = headers.get('authorization', '')
        if auth_header.startswith('Bearer ') and not auth_header.startswith('Bearer nexa-ak-'):
            jwt_token = auth_header[7:]
            claims = jwt_verify(jwt_token, config.session_secret)
            if claims:
                # JWT 认证通过
                if hasattr(request, 'auth_context'):
                    request.auth_context = {'type': 'jwt', 'claims': claims}
                return None

    # 认证失败 — 401
    # 与 ContractViolation 联动: 401 → requires 违反
    from .contracts import ContractViolation
    violation = ContractViolation(
        message='Authentication required',
        clause_type='requires',
        is_semantic=False,
    )

    return {
        'status': 401,
        'headers': {
            'location': config.failure_url,
            'content-type': 'text/plain',
        },
        'body': 'Authentication required',
        '_contract_violation': violation,
    }


# =============================================================================
# Agent API Key 管理 (Agent-Native 特色)
# =============================================================================

def agent_api_key_generate(agent_name: str, ttl: int = None) -> str:
    '''生成 Agent API Key — Agent-Native 特色 (学习自 NTNT + Nexa 差异化)

    格式: nexa-ak-{random32hex}

    Args:
        agent_name: Agent 名称
        ttl: 过期时间(秒), None 表示永不过期

    Returns:
        API Key 字符串
    '''
    random_hex = secrets.token_hex(16)  # 32 hex chars
    api_key = f'nexa-ak-{random_hex}'

    # 注册到全局 registry
    expires_at = int(time.time()) + ttl if ttl else 0  # 0 = 永不过期
    _api_key_registry[api_key] = {
        'agent_name': agent_name,
        'created_at': int(time.time()),
        'expires_at': expires_at,
    }

    return api_key


def agent_api_key_verify(api_key: str) -> Optional[Dict[str, Any]]:
    '''验证 Agent API Key

    Args:
        api_key: API Key 字符串

    Returns:
        Key 信息字典, 或 None (无效/过期)
    '''
    if not api_key.startswith('nexa-ak-'):
        return None

    key_info = _api_key_registry.get(api_key)
    if key_info is None:
        return None

    # 检查过期
    if key_info['expires_at'] > 0 and time.time() > key_info['expires_at']:
        # 过期 — 从 registry 删除
        _api_key_registry.pop(api_key, None)
        return None

    return {
        'type': 'api_key',
        'agent_name': key_info['agent_name'],
        'created_at': key_info['created_at'],
    }


def agent_auth_context(request: Any, agent: Any) -> Dict[str, Any]:
    '''Agent 认证上下文注入 — Agent-Native 特色

    将认证信息注入 Agent 的运行上下文, 用于:
    - system prompt 中注入用户身份
    - Agent memory 中融合 session 数据

    Args:
        request: NexaRequest 实例
        agent: NexaAgent 实例

    Returns:
        认证上下文字典
    '''
    user = get_user(request)
    session = get_session(request)

    context = {
        'authenticated': user is not None,
        'user': user,
        'session_data': session.data if session else {},
        'agent_name': getattr(agent, 'name', '') if agent else '',
    }

    # 检查 API Key 认证
    if hasattr(request, 'headers'):
        headers = request.headers if isinstance(request.headers, dict) else {}
        api_key = headers.get('x-api-key', headers.get('authorization', ''))
        if api_key.startswith('nexa-ak-') or api_key.startswith('Bearer nexa-ak-'):
            key_info = agent_api_key_verify(api_key.replace('Bearer ', '') if api_key.startswith('Bearer ') else api_key)
            if key_info:
                context['api_key_auth'] = key_info
                context['authenticated'] = True

    # 检查 JWT 认证
    if hasattr(request, 'headers'):
        headers = request.headers if isinstance(request.headers, dict) else {}
        auth_header = headers.get('authorization', '')
        if auth_header.startswith('Bearer ') and not auth_header.startswith('Bearer nexa-ak-'):
            claims = jwt_decode(auth_header[7:])
            if claims:
                context['jwt_auth'] = claims

    return context


# =============================================================================
# Session Store (学习自 NTNT storage.rs — Memory/SQLite)
# =============================================================================

class MemorySessionStore:
    '''内存 Session Store — 对应 NTNT MemorySessionStore

    dict-based, 支持过期清理
    '''
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            self.delete(session_id)
            return None
        return session

    def save(self, session: Session) -> None:
        self._sessions[session.id] = session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def cleanup_expired(self) -> int:
        '''清理过期 session'''
        expired_ids = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired_ids:
            self.delete(sid)
        return len(expired_ids)

    def count(self) -> int:
        return len(self._sessions)


class SQLiteSessionStore:
    '''SQLite Session Store — 对应 NTNT SQLiteSessionStore

    使用 Nexa 已有的 sqlite3, 创建 nexa_sessions 和 nexa_oauth_states 表
    '''
    def __init__(self, db_path: str = ':memory:'):
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        '''创建 session 和 oauth_states 表'''
        cursor = self._conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nexa_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT '',
                user_name TEXT NOT NULL DEFAULT '',
                user_email TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                csrf_token TEXT NOT NULL DEFAULT '',
                access_token TEXT NOT NULL DEFAULT '',
                refresh_token TEXT NOT NULL DEFAULT '',
                data_json TEXT NOT NULL DEFAULT '{}',
                expires_at INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nexa_oauth_states (
                state TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                redirect_url TEXT NOT NULL DEFAULT '',
                nonce TEXT NOT NULL DEFAULT '',
                pkce_verifier TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL DEFAULT 0
            )
        ''')
        self._conn.commit()

    def get(self, session_id: str) -> Optional[Session]:
        cursor = self._conn.cursor()
        cursor.execute('SELECT * FROM nexa_sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        if row is None:
            return None

        session = Session(
            id=row['id'],
            user_id=row['user_id'],
            user_name=row['user_name'],
            user_email=row['user_email'],
            provider=row['provider'],
            csrf_token=row['csrf_token'],
            access_token=row['access_token'],
            refresh_token=row['refresh_token'],
            data=json.loads(row['data_json']),
            expires_at=row['expires_at'],
            created_at=row['created_at'],
        )

        if session.is_expired():
            self.delete(session_id)
            return None

        return session

    def save(self, session: Session) -> None:
        cursor = self._conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO nexa_sessions
            (id, user_id, user_name, user_email, provider, csrf_token,
             access_token, refresh_token, data_json, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session.id,
            session.user_id,
            session.user_name,
            session.user_email,
            session.provider,
            session.csrf_token,
            session.access_token,
            session.refresh_token,
            json.dumps(session.data),
            session.expires_at,
            session.created_at,
        ))
        self._conn.commit()

    def delete(self, session_id: str) -> None:
        cursor = self._conn.cursor()
        cursor.execute('DELETE FROM nexa_sessions WHERE id = ?', (session_id,))
        self._conn.commit()

    def cleanup_expired(self) -> int:
        '''清理过期 session'''
        cursor = self._conn.cursor()
        now = int(time.time())
        cursor.execute('DELETE FROM nexa_sessions WHERE expires_at > 0 AND expires_at < ?', (now,))
        count = cursor.rowcount
        self._conn.commit()
        return count

    def count(self) -> int:
        cursor = self._conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM nexa_sessions')
        return cursor.fetchone()[0]

    def save_oauth_state(self, state: str, provider: str,
                          redirect_url: str = '', nonce: str = '',
                          pkce_verifier: str = '') -> None:
        '''保存 OAuth state (CSRF + PKCE verifier)'''
        cursor = self._conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO nexa_oauth_states
            (state, provider, redirect_url, nonce, pkce_verifier, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (state, provider, redirect_url, nonce, pkce_verifier, int(time.time())))
        self._conn.commit()

    def get_oauth_state(self, state: str) -> Optional[Dict[str, Any]]:
        '''获取 OAuth state'''
        cursor = self._conn.cursor()
        cursor.execute('SELECT * FROM nexa_oauth_states WHERE state = ?', (state,))
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            'state': row['state'],
            'provider': row['provider'],
            'redirect_url': row['redirect_url'],
            'nonce': row['nonce'],
            'pkce_verifier': row['pkce_verifier'],
            'created_at': row['created_at'],
        }

    def delete_oauth_state(self, state: str) -> None:
        '''删除 OAuth state (一次性使用)'''
        cursor = self._conn.cursor()
        cursor.execute('DELETE FROM nexa_oauth_states WHERE state = ?', (state,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# =============================================================================
# Auth 路由处理 (学习自 NTNT routes.rs — 与 HTTP Server 联动)
# =============================================================================

def handle_auth_start(request: Any, provider_name: str) -> Dict[str, Any]:
    '''Auth 路由: 启动 OAuth 流程 — 对应 NTNT auth_start

    Args:
        request: NexaRequest 实例
        provider_name: Provider 名称 ('google', 'github')

    Returns:
        redirect 响应 (到 OAuth Provider)
    '''
    config = _get_auth_config()

    # 查找 provider
    provider = None
    for p in config.providers:
        if p.name == provider_name:
            provider = p
            break

    if provider is None:
        return {
            'status': 400,
            'headers': {'content-type': 'text/plain'},
            'body': f'Unknown OAuth provider: {provider_name}',
        }

    # 生成 state (CSRF 防护)
    state = secrets.token_urlsafe(32)

    # 生成 nonce (OIDC)
    nonce = secrets.token_urlsafe(32)

    # 生成 PKCE (如果 provider 支持)
    pkce_challenge = None
    pkce_verifier = None
    if provider.use_pkce:
        pkce_verifier = generate_pkce_verifier()
        pkce_challenge = generate_pkce_challenge(pkce_verifier)

    # 确定 redirect_uri
    redirect_uri = ''
    if hasattr(request, 'headers'):
        headers = request.headers if isinstance(request.headers, dict) else {}
        host = headers.get('host', 'localhost:8080')
        protocol = headers.get('x-forwarded-proto', 'http')
        redirect_uri = f'{protocol}://{host}/auth/{provider_name}/callback'

    # 保存 state 到 session store (SQLite only)
    store = _get_session_store()
    if isinstance(store, SQLiteSessionStore):
        store.save_oauth_state(
            state=state,
            provider=provider_name,
            redirect_url=redirect_uri,
            nonce=nonce,
            pkce_verifier=pkce_verifier or '',
        )

    # 生成 authorization URL
    auth_url = generate_auth_url(
        provider=provider,
        redirect_uri=redirect_uri,
        state=state,
        nonce=nonce,
        pkce=pkce_challenge,
    )

    # 返回 redirect 响应
    return {
        'status': 302,
        'headers': {'location': auth_url},
        'body': '',
    }


def handle_auth_callback(request: Any, provider_name: str) -> Dict[str, Any]:
    '''Auth 路由: OAuth 回调处理 — 对应 NTNT auth_callback

    Args:
        request: NexaRequest 实例
        provider_name: Provider 名称

    Returns:
        设置 session + redirect 响应
    '''
    config = _get_auth_config()

    # 查找 provider
    provider = None
    for p in config.providers:
        if p.name == provider_name:
            provider = p
            break

    if provider is None:
        return {
            'status': 400,
            'headers': {'content-type': 'text/plain'},
            'body': f'Unknown OAuth provider: {provider_name}',
        }

    # 从请求获取 code 和 state
    code = ''
    state = ''
    if hasattr(request, 'query_params'):
        qp = request.query_params if isinstance(request.query_params, dict) else {}
        code = qp.get('code', '')
        state = qp.get('state', '')
    elif hasattr(request, 'query_string') and request.query_string:
        qs = parse_qs(request.query_string)
        code = qs.get('code', [''])[0]
        state = qs.get('state', [''])[0]

    # 验证 state (CSRF)
    store = _get_session_store()
    pkce_verifier = None
    redirect_uri = ''

    if isinstance(store, SQLiteSessionStore):
        state_info = store.get_oauth_state(state)
        if state_info is None:
            return {
                'status': 403,
                'headers': {'content-type': 'text/plain'},
                'body': 'Invalid OAuth state (possible CSRF attack)',
            }
        pkce_verifier = state_info.get('pkce_verifier', '') or None
        redirect_uri = state_info.get('redirect_url', '')
        # 删除 state (一次性使用)
        store.delete_oauth_state(state)

    # 交换 code for tokens
    if not redirect_uri:
        if hasattr(request, 'headers'):
            headers = request.headers if isinstance(request.headers, dict) else {}
            host = headers.get('host', 'localhost:8080')
            protocol = headers.get('x-forwarded-proto', 'http')
            redirect_uri = f'{protocol}://{host}/auth/{provider_name}/callback'

    token_response = exchange_code_for_tokens(
        provider=provider,
        code=code,
        redirect_uri=redirect_uri,
        pkce_verifier=pkce_verifier,
    )

    if not token_response.access_token:
        return {
            'status': 401,
            'headers': {'content-type': 'text/plain'},
            'body': 'OAuth token exchange failed',
        }

    # 获取 userinfo
    user_info = {}
    if HAS_REQUESTS and token_response.access_token:
        try:
            resp = http_requests.get(
                provider.userinfo_url,
                headers={'Authorization': f'Bearer {token_response.access_token}'},
                timeout=15,
            )
            user_info = resp.json()
        except Exception:
            user_info = {}

    # 创建 session
    session_id = secrets.token_urlsafe(32)
    csrf_nonce = secrets.token_hex(16)
    session = Session(
        id=session_id,
        user_id=str(user_info.get('id', user_info.get('sub', ''))),
        user_name=user_info.get('name', user_info.get('login', '')),
        user_email=user_info.get('email', ''),
        provider=provider_name,
        csrf_token=csrf_nonce,
        access_token=token_response.access_token,
        refresh_token=token_response.refresh_token,
        expires_at=int(time.time()) + config.session_ttl,
        data=user_info,
        created_at=int(time.time()),
    )

    # 保存 session
    store.save(session)

    # 签名 session ID
    signed_id = sign_session_id(session_id, config.session_secret)

    # 返回 redirect + set-cookie
    cookie_flags = f'Path=/; HttpOnly; SameSite={config.cookie_samesite}'
    if config.cookie_secure:
        cookie_flags += '; Secure'
    cookie_max_age = f'Max-Age={config.session_ttl}'

    return {
        'status': 302,
        'headers': {
            'location': config.success_url,
            'set-cookie': f'{config.cookie_name}={signed_id}; {cookie_flags}; {cookie_max_age}',
        },
        'body': '',
    }


def handle_auth_logout(request: Any) -> Dict[str, Any]:
    '''Auth 路由: 注销 — 对应 NTNT auth_logout

    Args:
        request: NexaRequest 实例

    Returns:
        清除 session + redirect 响应
    '''
    return logout_user(request)


# =============================================================================
# NexaAuth 统一入口 (学习自 NTNT auth.rs — 模块级 API)
# =============================================================================

def require_auth_middleware(request: Any) -> Any:
    '''require_auth 中间件适配器 — 适配 HTTP Server 中间件约定

    HTTP Server 中间件约定: None = 拒绝请求, 返回修改后的 request = 通过
    require_auth 约定: None = 认证通过, dict = 拒绝响应

    此函数将 require_auth 的约定转换为 HTTP Server 的约定:
    - require_auth 返回 None (通过) → 返回 request (通过)
    - require_auth 返回 dict (拒绝) → 返回 None (拒绝)

    Args:
        request: NexaRequest 实例

    Returns:
        修改后的 request (通过) 或 None (拒绝)
    '''
    result = require_auth(request)
    if result is None:
        # 认证通过 — 返回修改后的 request
        return request
    # 认证失败 — 返回 None (HTTP Server 约定: None = 拒绝)
    return None


class NexaAuth:
    '''Nexa Auth 统一入口 — 对应 NTNT Auth module

    提供所有 Auth API 的类封装, 方便在生成的代码中使用
    '''
    def __init__(self, config: AuthConfig = None):
        self.config = config or AuthConfig()
        global _global_auth_config, _global_session_store
        _global_auth_config = self.config
        if self.config.session_store == 'memory':
            _global_session_store = MemorySessionStore()
        elif self.config.session_store.startswith('sqlite:'):
            path = self.config.session_store[7:]
            _global_session_store = SQLiteSessionStore(path)
        else:
            _global_session_store = MemorySessionStore()

    def oauth(self, name: str, client_id: str, client_secret: str,
              opts: Dict[str, Any] = None) -> ProviderConfig:
        return oauth(name, client_id, client_secret, opts)

    def get_user(self, request: Any) -> Optional[Dict[str, Any]]:
        return get_user(request)

    def get_session(self, request: Any) -> Optional[Session]:
        return get_session(request)

    def require_auth(self, request: Any) -> Optional[Dict[str, Any]]:
        return require_auth(request)

    def logout_user(self, request: Any) -> Dict[str, Any]:
        return logout_user(request)

    def jwt_sign(self, claims: Dict[str, Any], secret: str,
                 options: Dict[str, Any] = None) -> str:
        return jwt_sign(claims, secret, options)

    def jwt_verify(self, token: str, secret: str) -> Optional[Dict[str, Any]]:
        return jwt_verify(token, secret)

    def jwt_decode(self, token: str) -> Dict[str, Any]:
        return jwt_decode(token)

    def csrf_token(self, request: Any) -> str:
        return csrf_token(request)

    def csrf_field(self, request: Any) -> str:
        return csrf_field(request)

    def verify_csrf(self, request: Any, token: str) -> bool:
        return verify_csrf(request, token)

    def agent_api_key_generate(self, agent_name: str, ttl: int = None) -> str:
        return agent_api_key_generate(agent_name, ttl)

    def agent_api_key_verify(self, api_key: str) -> Optional[Dict[str, Any]]:
        return agent_api_key_verify(api_key)

    def agent_auth_context(self, request: Any, agent: Any) -> Dict[str, Any]:
        return agent_auth_context(request, agent)