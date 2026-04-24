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

"""
Nexa RBAC 权限访问控制系统 (Role-Based Access Control)
为不同 Agent 或流定义安全角色，确保工具调用的最小权限原则
"""

import os
import json
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
from functools import wraps
import threading


class Permission(Enum):
    """权限枚举"""
    # 工具执行权限
    TOOL_EXECUTE = "tool:execute"
    TOOL_READ = "tool:read"
    TOOL_WRITE = "tool:write"
    
    # Agent 操作权限
    AGENT_RUN = "agent:run"
    AGENT_CREATE = "agent:create"
    AGENT_DELETE = "agent:delete"
    AGENT_CLONE = "agent:clone"
    
    # 记忆访问权限
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_DELETE = "memory:delete"
    
    # 配置权限
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"
    
    # 管理权限
    ADMIN_ALL = "admin:all"
    ROLE_MANAGE = "role:manage"
    AUDIT_VIEW = "audit:view"


@dataclass
class Role:
    """角色定义"""
    name: str
    description: str
    permissions: Set[Permission] = field(default_factory=set)
    inherits: List[str] = field(default_factory=list)  # 继承的角色名
    constraints: Dict[str, Any] = field(default_factory=dict)  # 约束条件
    
    def has_permission(self, permission: Permission) -> bool:
        """检查是否有指定权限"""
        return permission in self.permissions or Permission.ADMIN_ALL in self.permissions
        
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "permissions": [p.value for p in self.permissions],
            "inherits": self.inherits,
            "constraints": self.constraints
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Role':
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            permissions={Permission(p) for p in data.get("permissions", [])},
            inherits=data.get("inherits", []),
            constraints=data.get("constraints", {})
        )


@dataclass
class SecurityContext:
    """安全上下文"""
    agent_name: str
    roles: List[str]
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    allowed_tools: Set[str] = field(default_factory=set)
    denied_tools: Set[str] = field(default_factory=set)
    rate_limits: Dict[str, int] = field(default_factory=dict)  # tool -> max_calls_per_minute


class RBACManager:
    """
    RBAC 权限管理器
    
    特性：
    - 角色管理：定义和管理安全角色
    - 权限检查：验证操作权限
    - 继承支持：角色可以继承其他角色的权限
    - 约束条件：支持时间、资源等约束
    - 审计日志：记录权限检查和访问
    """
    
    # 预定义角色
    BUILTIN_ROLES = {
        "admin": Role(
            name="admin",
            description="管理员角色，拥有所有权限",
            permissions={Permission.ADMIN_ALL}
        ),
        "agent_standard": Role(
            name="agent_standard",
            description="标准智能体角色",
            permissions={
                Permission.AGENT_RUN,
                Permission.TOOL_EXECUTE,
                Permission.TOOL_READ,
                Permission.MEMORY_READ,
                Permission.MEMORY_WRITE,
                Permission.CONFIG_READ
            }
        ),
        "agent_readonly": Role(
            name="agent_readonly",
            description="只读智能体角色",
            permissions={
                Permission.AGENT_RUN,
                Permission.TOOL_READ,
                Permission.MEMORY_READ,
                Permission.CONFIG_READ
            }
        ),
        "agent_tool_user": Role(
            name="agent_tool_user",
            description="工具使用角色",
            permissions={
                Permission.TOOL_EXECUTE,
                Permission.TOOL_READ
            }
        ),
        "agent_memory_manager": Role(
            name="agent_memory_manager",
            description="记忆管理角色",
            permissions={
                Permission.MEMORY_READ,
                Permission.MEMORY_WRITE,
                Permission.MEMORY_DELETE
            }
        ),
        "flow_orchestrator": Role(
            name="flow_orchestrator",
            description="流程编排角色",
            permissions={
                Permission.AGENT_RUN,
                Permission.AGENT_CREATE,
                Permission.TOOL_EXECUTE,
                Permission.CONFIG_READ
            }
        ),
        "auditor": Role(
            name="auditor",
            description="审计角色",
            permissions={
                Permission.AUDIT_VIEW,
                Permission.CONFIG_READ,
                Permission.MEMORY_READ
            }
        )
    }
    
    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path or ".nexa_security/rbac_config.json")
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.roles: Dict[str, Role] = {}
        self.agent_roles: Dict[str, List[str]] = {}  # agent_name -> [role_names]
        self.contexts: Dict[str, SecurityContext] = {}
        self.audit_log: List[Dict] = []
        self._lock = threading.RLock()
        
        # 加载内置角色
        self.roles.update(self.BUILTIN_ROLES)
        
        # 加载自定义配置
        self._load_config()
        
    def _load_config(self):
        """加载配置文件"""
        if not self.config_path.exists():
            return
            
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            # 加载自定义角色
            for role_data in config.get("roles", []):
                role = Role.from_dict(role_data)
                self.roles[role.name] = role
                
            # 加载 Agent 角色映射
            self.agent_roles = config.get("agent_roles", {})
            
        except Exception as e:
            print(f"[RBACManager] Warning: Failed to load config: {e}")
            
    def _save_config(self):
        """保存配置文件"""
        try:
            config = {
                "roles": [r.to_dict() for r in self.roles.values() if r.name not in self.BUILTIN_ROLES],
                "agent_roles": self.agent_roles
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[RBACManager] Warning: Failed to save config: {e}")
            
    def create_role(
        self,
        name: str,
        description: str,
        permissions: List[Permission],
        inherits: List[str] = None,
        constraints: Dict = None
    ) -> Role:
        """创建新角色"""
        with self._lock:
            role = Role(
                name=name,
                description=description,
                permissions=set(permissions),
                inherits=inherits or [],
                constraints=constraints or {}
            )
            self.roles[name] = role
            self._save_config()
            return role
            
    def delete_role(self, name: str) -> bool:
        """删除角色"""
        with self._lock:
            if name in self.BUILTIN_ROLES:
                return False  # 不能删除内置角色
            if name in self.roles:
                del self.roles[name]
                # 清理 Agent 角色映射
                for agent, roles in self.agent_roles.items():
                    if name in roles:
                        roles.remove(name)
                self._save_config()
                return True
            return False
            
    def get_role(self, name: str) -> Optional[Role]:
        """获取角色"""
        return self.roles.get(name)
        
    def get_effective_permissions(self, role_names: List[str]) -> Set[Permission]:
        """获取有效权限（包括继承的权限）"""
        effective = set()
        processed = set()
        
        def collect_permissions(role_name: str):
            if role_name in processed:
                return
            processed.add(role_name)
            
            role = self.roles.get(role_name)
            if role:
                effective.update(role.permissions)
                for inherited in role.inherits:
                    collect_permissions(inherited)
                    
        for role_name in role_names:
            collect_permissions(role_name)
            
        return effective
        
    def assign_role(self, agent_name: str, role_name: str) -> bool:
        """为 Agent 分配角色"""
        with self._lock:
            if role_name not in self.roles:
                return False
                
            if agent_name not in self.agent_roles:
                self.agent_roles[agent_name] = []
                
            if role_name not in self.agent_roles[agent_name]:
                self.agent_roles[agent_name].append(role_name)
                self._save_config()
                
            return True
            
    def revoke_role(self, agent_name: str, role_name: str) -> bool:
        """撤销 Agent 的角色"""
        with self._lock:
            if agent_name in self.agent_roles and role_name in self.agent_roles[agent_name]:
                self.agent_roles[agent_name].remove(role_name)
                self._save_config()
                return True
            return False
            
    def get_agent_roles(self, agent_name: str) -> List[Role]:
        """获取 Agent 的所有角色"""
        role_names = self.agent_roles.get(agent_name, [])
        return [self.roles[name] for name in role_names if name in self.roles]
        
    def check_permission(
        self,
        agent_name: str,
        permission: Permission,
        resource: str = None,
        context: Dict = None
    ) -> bool:
        """
        检查 Agent 是否有指定权限
        
        Args:
            agent_name: Agent 名称
            permission: 权限
            resource: 资源标识（可选）
            context: 上下文信息（可选）
            
        Returns:
            是否有权限
        """
        with self._lock:
            role_names = self.agent_roles.get(agent_name, [])
            effective_permissions = self.get_effective_permissions(role_names)
            
            has_perm = permission in effective_permissions or Permission.ADMIN_ALL in effective_permissions
            
            # 记录审计日志
            self._log_audit(
                agent_name=agent_name,
                permission=permission.value,
                resource=resource,
                granted=has_perm,
                context=context
            )
            
            return has_perm
            
    def check_tool_access(self, agent_name: str, tool_name: str, action: str = "execute") -> bool:
        """检查工具访问权限"""
        # 获取 Agent 的安全上下文
        ctx = self.contexts.get(agent_name)
        
        if ctx:
            # 检查明确拒绝的工具
            if tool_name in ctx.denied_tools:
                self._log_audit(
                    agent_name=agent_name,
                    permission=f"tool:{action}",
                    resource=tool_name,
                    granted=False,
                    reason="Tool explicitly denied"
                )
                return False
                
            # 检查明确允许的工具
            if ctx.allowed_tools and tool_name not in ctx.allowed_tools:
                # 检查通配符
                allowed = False
                for pattern in ctx.allowed_tools:
                    if pattern.endswith("*") and tool_name.startswith(pattern[:-1]):
                        allowed = True
                        break
                if not allowed:
                    self._log_audit(
                        agent_name=agent_name,
                        permission=f"tool:{action}",
                        resource=tool_name,
                        granted=False,
                        reason="Tool not in allowed list"
                    )
                    return False
                    
        # 检查角色权限
        permission = {
            "execute": Permission.TOOL_EXECUTE,
            "read": Permission.TOOL_READ,
            "write": Permission.TOOL_WRITE
        }.get(action, Permission.TOOL_EXECUTE)
        
        return self.check_permission(agent_name, permission, tool_name)
        
    def create_security_context(
        self,
        agent_name: str,
        session_id: str = None,
        allowed_tools: List[str] = None,
        denied_tools: List[str] = None,
        rate_limits: Dict[str, int] = None
    ) -> SecurityContext:
        """创建安全上下文"""
        with self._lock:
            context = SecurityContext(
                agent_name=agent_name,
                roles=self.agent_roles.get(agent_name, []),
                session_id=session_id or f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                allowed_tools=set(allowed_tools or []),
                denied_tools=set(denied_tools or []),
                rate_limits=rate_limits or {}
            )
            self.contexts[agent_name] = context
            return context
            
    def get_security_context(self, agent_name: str) -> Optional[SecurityContext]:
        """获取安全上下文"""
        return self.contexts.get(agent_name)
        
    def _log_audit(
        self,
        agent_name: str,
        permission: str,
        resource: str = None,
        granted: bool = True,
        reason: str = None,
        context: Dict = None
    ):
        """记录审计日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "permission": permission,
            "resource": resource,
            "granted": granted,
            "reason": reason,
            "context": context
        }
        self.audit_log.append(entry)
        
        # 限制日志大小
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-5000:]
            
    def get_audit_log(
        self,
        agent_name: str = None,
        permission: str = None,
        granted: bool = None,
        limit: int = 100
    ) -> List[Dict]:
        """获取审计日志"""
        logs = self.audit_log
        
        if agent_name:
            logs = [l for l in logs if l["agent"] == agent_name]
        if permission:
            logs = [l for l in logs if l["permission"] == permission]
        if granted is not None:
            logs = [l for l in logs if l["granted"] == granted]
            
        return logs[-limit:]
        
    def export_audit_log(self, path: str):
        """导出审计日志"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.audit_log, f, ensure_ascii=False, indent=2)
            

def require_permission(permission: Permission):
    """权限检查装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 尝试从参数中获取 agent_name
            agent_name = kwargs.get("agent_name") or (args[0] if args else None)
            
            if agent_name:
                rbac = get_rbac_manager()
                if not rbac.check_permission(agent_name, permission):
                    raise PermissionError(
                        f"Agent '{agent_name}' does not have permission: {permission.value}"
                    )
                    
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_tool_access(tool_name: str, action: str = "execute"):
    """工具访问检查装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            agent_name = kwargs.get("agent_name") or (args[0] if args else None)
            
            if agent_name:
                rbac = get_rbac_manager()
                if not rbac.check_tool_access(agent_name, tool_name, action):
                    raise PermissionError(
                        f"Agent '{agent_name}' cannot {action} tool: {tool_name}"
                    )
                    
            return func(*args, **kwargs)
        return wrapper
    return decorator


# 全局 RBAC 管理器
_global_rbac_manager: Optional[RBACManager] = None


def get_rbac_manager() -> RBACManager:
    """获取全局 RBAC 管理器"""
    global _global_rbac_manager
    if _global_rbac_manager is None:
        _global_rbac_manager = RBACManager()
    return _global_rbac_manager


def init_rbac(config_path: str = None) -> RBACManager:
    """初始化 RBAC 管理器"""
    global _global_rbac_manager
    _global_rbac_manager = RBACManager(config_path)
    return _global_rbac_manager


__all__ = [
    'RBACManager', 'Role', 'SecurityContext', 'Permission',
    'require_permission', 'require_tool_access',
    'get_rbac_manager', 'init_rbac'
]