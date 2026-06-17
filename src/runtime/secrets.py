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

import os
import pathlib
import re
import ast
from typing import Any, Dict, Optional

class ConfigNode:
    def __init__(self, data=None):
        self._data = data or {}

    def __getattr__(self, name):
        if name in self._data:
            val = self._data[name]
            if isinstance(val, dict):
                return ConfigNode(val)
            return val
        return os.environ.get(name, "")

    def __getitem__(self, name):
        return self.__getattr__(name)

    def get(self, name: str, default: str = ""):
        """Explicit get method with default value"""
        val = self._data.get(name)
        if val is None:
            return os.environ.get(name, default)
        if isinstance(val, dict):
            return ConfigNode(val)
        return val

    def __str__(self):
        return str(self._data)

    def __repr__(self):
        return f"ConfigNode({self._data})"


class NexaSecrets:
    """
    负责管理 Nexa 的秘钥 (.nxs 文件) 和环境变量
    
    支持两种 secrets.nxs 格式:
    
    1. 扁平格式 (旧格式):
       OPENAI_API_KEY = "<openai-api-key>"
       OPENAI_API_BASE = "https://api.openai.com/v1"
    
    2. Config Block 格式 (新格式):
       config default {
           BASE_URL = "https://aihub.arcsysu.cn/v1",
           API_KEY = "<provider-api-key>",
           MODEL_NAME = {
               "strong": "minimax-m2.5",
               "weak": "deepseek-chat"
           }
       }
    """
    
    def __init__(self):
        self._flat_configs: Dict[str, Any] = {}  # 扁平格式: KEY -> VALUE
        self._block_configs: Dict[str, ConfigNode] = {}  # Block 格式: config_name -> ConfigNode
        self._load_secrets()
        
    def _parse_nxs(self, content: str) -> tuple:
        """
        解析 secrets.nxs 文件，支持两种格式
        返回: (block_configs, flat_configs)
        """
        # Strip full line comments
        content = re.sub(r'^\s*//.*', '', content, flags=re.MULTILINE)
        
        block_configs = {}
        block_spans = []
        flat_configs = {}
        
        # 1. 解析 config block 格式
        idx = 0
        while idx < len(content):
            match = re.search(r'config\s+([a-zA-Z0-9_]+)\s*\{', content[idx:])
            if not match:
                break
                
            config_name = match.group(1)
            start_brace = idx + match.end() - 1
            
            # find matching end brace
            brace_count = 0
            end_brace = -1
            for i in range(start_brace, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_brace = i
                        break
                        
            if end_brace == -1:
                break
                
            config_body = content[start_brace+1:end_brace]
            block_spans.append((idx + match.start(), end_brace + 1))
            idx = end_brace + 1
            
            # Parse block content
            parsed_block = self._parse_block_content(config_body)
            block_configs[config_name] = ConfigNode(parsed_block)
        
        # 2. 解析扁平格式 (不在 config 块内的 KEY = VALUE)
        # 移除所有 config 块，只保留块外的内容
        content_parts = []
        last_idx = 0
        for start, end in block_spans:
            content_parts.append(content[last_idx:start])
            last_idx = end
        content_parts.append(content[last_idx:])
        content_without_blocks = ''.join(content_parts)
        
        # 解析剩余的扁平赋值
        flat_configs = self._parse_flat_content(content_without_blocks)
        
        return block_configs, flat_configs
    
    def _parse_block_content(self, body: str) -> dict:
        """解析 config block 内的内容，不执行任意 Python 代码。"""
        result: Dict[str, Any] = {}
        pending_key: Optional[str] = None
        pending_value_lines: list[str] = []
        brace_balance = 0
        bracket_balance = 0

        for raw_line in body.split('\n'):
            line = raw_line.strip()
            if not line or line.startswith('//'):
                continue

            if pending_key is None:
                match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)$', line)
                if not match:
                    continue
                key = match.group(1)
                value_part = match.group(2).strip()
                pending_key = key
                pending_value_lines = [value_part]
            else:
                pending_value_lines.append(line)

            joined = '\n'.join(pending_value_lines)
            brace_balance = joined.count('{') - joined.count('}')
            bracket_balance = joined.count('[') - joined.count(']')
            if brace_balance > 0 or bracket_balance > 0:
                continue

            value_text = self._strip_assignment_delimiter(joined)
            result[pending_key] = self._parse_literal_value(value_text)
            pending_key = None
            pending_value_lines = []

        if pending_key is not None:
            result[pending_key] = self._parse_literal_value(self._strip_assignment_delimiter('\n'.join(pending_value_lines)))

        return result

    def _strip_assignment_delimiter(self, value_str: str) -> str:
        """Remove a trailing top-level comma used between config entries."""
        normalized = value_str.strip()
        if normalized.endswith(","):
            return normalized[:-1].rstrip()
        return normalized

    def _parse_literal_value(self, value_str: str) -> Any:
        """Parse a .nxs literal value without executing code."""
        normalized = value_str.strip()
        lowered = normalized.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered in ("null", "none"):
            return None
        try:
            return ast.literal_eval(normalized)
        except (ValueError, SyntaxError):
            if re.match(r'^[A-Za-z0-9_./:\-]+$', normalized):
                return normalized
            raise ValueError("Invalid .nxs literal value")
    
    def _parse_flat_content(self, content: str) -> dict:
        """解析扁平格式的 KEY = VALUE"""
        flat = {}
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            
            # Match: KEY = "value" or KEY = value
            match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]+)\s*=\s*(.+)$', line)
            if match:
                key = match.group(1)
                value_str = match.group(2).strip()
                
                try:
                    value = self._parse_literal_value(value_str)
                except ValueError:
                    value = value_str

                flat[key] = value
        
        return flat

    def _load_secrets(self):
        """
        加载 secrets.nxs 文件
        
        搜索策略（覆盖法）：
        1. 从当前工作目录开始，向上逐级搜索 *.nxs 文件
        2. 优先使用最近的（子目录优先于父目录）
        3. 合并所有找到的 .nxs 文件中的 config blocks
        """
        # 收集所有 .nxs 文件（从当前目录向上搜索）
        nxs_files = []
        current_dir = pathlib.Path.cwd()
        
        # 向上搜索，最多搜索 10 级目录
        for _ in range(10):
            # 查找当前目录下的所有 .nxs 文件
            for nxs_file in current_dir.glob("*.nxs"):
                nxs_files.append(nxs_file)
            
            # 移动到父目录
            parent = current_dir.parent
            if parent == current_dir:  # 已到达根目录
                break
            current_dir = parent
        
        if not nxs_files:
            if os.environ.get("NEXA_DEBUG"):
                print("[Secrets] No .nxs files found")
            return
        
        # 合并所有 .nxs 文件的配置
        all_block_configs = {}
        all_flat_configs = {}
        
        for nxs_file in nxs_files:
            try:
                with open(nxs_file, "r", encoding="utf-8") as f:
                    content = f.read()
                block_configs, flat_configs = self._parse_nxs(content)
                
                # 合并配置（后面的文件覆盖前面的）
                all_block_configs.update(block_configs)
                all_flat_configs.update(flat_configs)
                
                if os.environ.get("NEXA_DEBUG"):
                    print(f"[Secrets] Loaded from: {nxs_file}")
                    print(f"[Secrets] Block configs: {list(block_configs.keys())}")
                    print(f"[Secrets] Flat configs: {list(flat_configs.keys())}")
            except Exception as e:
                if os.environ.get("NEXA_DEBUG"):
                    print(f"[Secrets] Error loading {nxs_file}: {e}")
        
        self._block_configs = all_block_configs
        self._flat_configs = all_flat_configs
        self._active_config = "default"  # 默认使用 "default" config
        
        if os.environ.get("NEXA_DEBUG"):
            print(f"[Secrets] Total block configs: {list(self._block_configs.keys())}")
            print(f"[Secrets] Total flat configs: {list(self._flat_configs.keys())}")
            print(f"[Secrets] Active config: {self._active_config}")

    def load_from_script_dir(self, script_path: str) -> None:
        """
        从脚本所在目录加载 .nxs 文件，合并到已有配置中。
        由生成的 Python 代码在运行时调用。
        
        Args:
            script_path: 当前脚本的文件路径（__file__）
        """
        script_dir = pathlib.Path(script_path).resolve().parent
        
        # 从脚本目录向上搜索 .nxs 文件
        nxs_files = []
        current_dir = script_dir
        
        for _ in range(10):
            for nxs_file in current_dir.glob("*.nxs"):
                if nxs_file not in nxs_files:
                    nxs_files.append(nxs_file)
            parent = current_dir.parent
            if parent == current_dir:
                break
            current_dir = parent
        
        for nxs_file in nxs_files:
            try:
                with open(nxs_file, "r", encoding="utf-8") as f:
                    content = f.read()
                block_configs, flat_configs = self._parse_nxs(content)
                self._block_configs.update(block_configs)
                self._flat_configs.update(flat_configs)
                
                if os.environ.get("NEXA_DEBUG"):
                    print(f"[Secrets] Loaded from script dir: {nxs_file}")
                    print(f"[Secrets] Block configs: {list(block_configs.keys())}")
            except Exception as e:
                if os.environ.get("NEXA_DEBUG"):
                    print(f"[Secrets] Error loading {nxs_file}: {e}")
        
        if os.environ.get("NEXA_DEBUG"):
            print(f"[Secrets] Total block configs after script dir load: {list(self._block_configs.keys())}")

    def select_config(self, config_name: str) -> bool:
        """
        选择要使用的 config block
        
        Args:
            config_name: config block 的名称（如 "default", "ali", "openai"）
            
        Returns:
            True 如果成功切换，False 如果 config 不存在
        """
        if config_name in self._block_configs:
            self._active_config = config_name
            if os.environ.get("NEXA_DEBUG"):
                print(f"[Secrets] Switched to config: {config_name}")
            return True
        else:
            if os.environ.get("NEXA_DEBUG"):
                print(f"[Secrets] Config '{config_name}' not found, available: {list(self._block_configs.keys())}")
            return False
    
    def get_active_config_name(self) -> str:
        """获取当前激活的 config 名称"""
        return self._active_config

    def __getattr__(self, name):
        """访问 config block"""
        if name in self._block_configs:
            return self._block_configs[name]
        return ConfigNode()

    def get(self, key: str, default: str = "") -> str:
        """
        获取配置值，按以下优先级查找:
        1. 当前激活的 config block 中的值
        2. default config block 中的值（如果激活的不是 default）
        3. 扁平格式中的值
        4. 环境变量
        
        Args:
            key: 配置键名 (如 API_KEY, BASE_URL, OPENAI_API_KEY)
            default: 默认值
            
        Returns:
            配置值字符串
        """
        # 1. 先查当前激活的 config block
        if self._active_config in self._block_configs:
            val = self._block_configs[self._active_config].get(key, None)
            if val is not None and not isinstance(val, ConfigNode):
                return str(val)
            elif isinstance(val, ConfigNode):
                # 如果是嵌套 ConfigNode，返回空字符串（需要用属性访问）
                pass
        
        # 2. 如果激活的不是 default，再查 default config block
        if self._active_config != "default" and "default" in self._block_configs:
            val = self._block_configs["default"].get(key, None)
            if val is not None and not isinstance(val, ConfigNode):
                return str(val)
        
        # 3. 再查 flat configs
        if key in self._flat_configs:
            val = self._flat_configs[key]
            if not isinstance(val, dict):
                return str(val)
        
        # 4. 最后查环境变量
        return os.environ.get(key, default)
    
    def get_model_config(self) -> Dict[str, str]:
        """
        获取模型配置
        
        Returns:
            {"strong": "...", "weak": "...", "super": "..."} 或默认值
        """
        default_models = {
            "strong": "gpt-4",
            "weak": "gpt-3.5-turbo",
            "super": "gpt-4"
        }
        
        # 从当前激活的 config block 获取
        if self._active_config in self._block_configs:
            model_node = self._block_configs[self._active_config].MODEL_NAME
            if isinstance(model_node, ConfigNode):
                return {
                    "strong": model_node.get("strong", default_models["strong"]),
                    "weak": model_node.get("weak", default_models["weak"]),
                    "super": model_node.get("super", default_models["super"])
                }
        
        # 如果激活的不是 default，再查 default config block
        if self._active_config != "default" and "default" in self._block_configs:
            model_node = self._block_configs["default"].MODEL_NAME
            if isinstance(model_node, ConfigNode):
                return {
                    "strong": model_node.get("strong", default_models["strong"]),
                    "weak": model_node.get("weak", default_models["weak"]),
                    "super": model_node.get("super", default_models["super"])
                }
        
        return default_models
    
    def get_provider_config(self, provider: str) -> tuple:
        """
        获取特定 provider 的配置
        
        Args:
            provider: 提供商名称 (如 openai, deepseek, minimax)
            
        Returns:
            (api_key, base_url) tuple
        """
        # 1. 先查 active config block 中的 API_KEY 和 BASE_URL
        if self._active_config in self._block_configs:
            block = self._block_configs[self._active_config]
            api_key = block.get("API_KEY", "")
            base_url = block.get("BASE_URL", "")
            if api_key or base_url:
                return api_key, base_url
        
        # 2. 查 provider 特定的 config block
        if provider in self._block_configs:
            block = self._block_configs[provider]
            api_key = block.get("API_KEY", "")
            base_url = block.get("BASE_URL", "")
            if api_key or base_url:
                return api_key, base_url
        
        # 3. 查 provider 特定的环境变量格式
        api_key = self.get(f"{provider.upper()}_API_KEY")
        base_url = self.get(f"{provider.upper()}_BASE_URL")
        
        if api_key or base_url:
            return api_key, base_url
        
        # 4. Fallback 到 default config
        return self.get("API_KEY"), self.get("BASE_URL")

# 单例实例
nexa_secrets = NexaSecrets()
