"""
Nexa 项目配置文件 (nexa.toml) 加载器

配置优先级: CLI flag > 环境变量 > nexa.toml > 默认值

nexa.toml 格式示例:
```toml
[project]
name = "my-nexa-app"
version = "0.1.0"

[type]
mode = "warn"           # strict / warn / forgiving

[lint]
mode = "default"        # default / warn / strict

[agent]
default_model = "minimax-m2.5"
default_timeout = 30
default_retry = 3

[runtime]
cache_dir = ".nexa_cache"
memory_backend = "sqlite"
```
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("nexa.config")

# 全局缓存 — 只加载一次
_config_cache: Optional[Dict] = None
_config_path: Optional[Path] = None


def find_nexa_toml() -> Optional[Path]:
    """查找 nexa.toml 配置文件
    
    搜索顺序:
    1. 当前工作目录
    2. 项目根目录 (向上查找，直到找到 .git 或 nexa.toml)
    3. 用户 HOME 目录
    
    Returns:
        Path 对象或 None (如果找不到)
    """
    # 1. 当前工作目录
    cwd = Path.cwd()
    candidate = cwd / "nexa.toml"
    if candidate.exists():
        return candidate
    
    # 2. 向上查找项目根目录
    for parent in cwd.parents:
        candidate = parent / "nexa.toml"
        if candidate.exists():
            return candidate
        # 如果找到 .git 目录，认为到达项目根
        if (parent / ".git").exists():
            break
    
    # 3. 用户 HOME 目录
    home = Path.home()
    candidate = home / "nexa.toml"
    if candidate.exists():
        return candidate
    
    return None


def load_nexa_config(force_reload: bool = False) -> Dict[str, Any]:
    """加载 nexa.toml 配置文件
    
    使用全局缓存避免重复加载。
    
    Args:
        force_reload: 是否强制重新加载
    
    Returns:
        配置字典 (如果找不到配置文件，返回空字典)
    """
    global _config_cache, _config_path
    
    if _config_cache is not None and not force_reload:
        return _config_cache
    
    config_path = find_nexa_toml()
    if config_path is None:
        _config_cache = {}
        _config_path = None
        return _config_cache
    
    _config_path = config_path
    
    try:
        config_content = config_path.read_text(encoding="utf-8")
        config = _parse_toml(config_content)
        _config_cache = config
        logger.debug(f"Loaded nexa.toml from {config_path}")
        return config
    except Exception as e:
        logger.warning(f"Failed to load nexa.toml from {config_path}: {e}")
        _config_cache = {}
        return _config_cache


def _parse_toml(content: str) -> Dict[str, Any]:
    """简化的 TOML 解析器
    
    不依赖第三方库，支持基本的 TOML 格式:
    - [section] 头
    - key = "value" 字符串值
    - key = 123 整数值
    - key = 12.3 浮点数值
    - key = true/false 布尔值
    - # 注释
    
    Args:
        content: TOML 文件内容字符串
    
    Returns:
        解析后的配置字典
    """
    config: Dict[str, Any] = {}
    current_section = config
    
    for line in content.split("\n"):
        line = line.strip()
        
        # 空行和注释
        if not line or line.startswith("#"):
            continue
        
        # Section 头: [section] 或 [section.subsection]
        if line.startswith("["):
            section_name = line[1:line.index("]")].strip()
            current_section = config
            for part in section_name.split("."):
                if part not in current_section:
                    current_section[part] = {}
                current_section = current_section[part]
            continue
        
        # key = value
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            
            # 移除注释 (value 后的 # 注释)
            # 对于引号字符串值: 先找到闭合引号，再移除后面的注释
            # 对于非引号值: 直接移除 # 后的内容
            if value.startswith('"'):
                # 找到闭合引号的位置，移除后面的注释
                end_quote = value.find('"', 1)
                if end_quote != -1:
                    # 剥离引号内容，忽略尾部注释
                    value = value[:end_quote + 1]
            elif value.startswith("'"):
                end_quote = value.find("'", 1)
                if end_quote != -1:
                    value = value[:end_quote + 1]
            elif "#" in value:
                # 非引号值：移除尾部注释
                value = value[:value.index("#")].strip()
            
            # 解析值类型
            if value.startswith('"') and value.endswith('"'):
                # 字符串值
                current_section[key] = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                # 字符串值 (单引号)
                current_section[key] = value[1:-1]
            elif value.lower() == "true":
                current_section[key] = True
            elif value.lower() == "false":
                current_section[key] = False
            elif "." in value and value.replace(".", "", 1).replace("-", "", 1).isdigit():
                current_section[key] = float(value)
            elif value.replace("-", "", 1).isdigit():
                current_section[key] = int(value)
            else:
                # 未知类型 — 保留原始字符串
                current_section[key] = value
    
    return config


def get_config_value(section: str, key: str, default: Any = None) -> Any:
    """获取配置值
    
    Args:
        section: 配置段名 (如 "type", "lint", "agent")
        key: 配置键名 (如 "mode", "default_model")
        default: 默认值
    
    Returns:
        配置值或默认值
    """
    config = load_nexa_config()
    section_config = config.get(section, {})
    return section_config.get(key, default)


def get_effective_type_mode(cli_override: Optional[str] = None) -> str:
    """获取有效的类型检查模式
    
    优先级: CLI > 环境变量 > nexa.toml > 默认值(warn)
    
    Returns:
        模式字符串 ("strict" / "warn" / "forgiving")
    """
    from .type_system import TypeMode, get_type_mode
    mode = get_type_mode(cli_override=cli_override)
    return mode.value


def get_effective_lint_mode(cli_override: Optional[str] = None) -> str:
    """获取有效的 lint 模式
    
    优先级: CLI > 环境变量 > nexa.toml > 默认值(default)
    
    Returns:
        模式字符串 ("default" / "warn" / "strict")
    """
    from .type_system import LintMode, get_lint_mode
    mode = get_lint_mode(cli_override=cli_override)
    return mode.value


def create_default_nexa_toml(path: Optional[Path] = None) -> Path:
    """创建默认的 nexa.toml 配置文件
    
    Args:
        path: 目标路径 (默认为当前目录的 nexa.toml)
    
    Returns:
        创建的文件路径
    """
    if path is None:
        path = Path.cwd() / "nexa.toml"
    
    default_content = """# Nexa Project Configuration
# https://nexa-lang.org/docs/configuration

[project]
name = "my-nexa-app"
version = "0.1.0"

# 渐进式类型系统配置 (Gradual Type System)
# NEXA_TYPE_MODE 环境变量可覆盖此配置
# 优先级: CLI flag > 环境变量 > nexa.toml > 默认值
[type]
mode = "warn"           # strict / warn / forgiving
# strict:    类型不匹配=运行时错误，程序终止
# warn:      类型不匹配=日志警告并继续（默认）
# forgiving: 类型不匹配=静默忽略

# Lint 类型检查配置
# NEXA_LINT_MODE 环境变量可覆盖此配置
[lint]
mode = "default"        # default / warn / strict
# default: 只检查有类型标注的代码（默认）
# warn:    对缺失类型标注发出警告
# strict:  缺失类型标注=lint错误（非零退出码）

[agent]
default_model = "minimax-m2.5"
default_timeout = 30
default_retry = 3

[runtime]
cache_dir = ".nexa_cache"
"""
    
    path.write_text(default_content, encoding="utf-8")
    logger.info(f"Created default nexa.toml at {path}")
    return path