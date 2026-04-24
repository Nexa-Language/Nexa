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
       OPENAI_API_KEY = "sk-xxx"
       OPENAI_API_BASE = "https://api.openai.com/v1"
    
    2. Config Block 格式 (新格式):
       config default {
           BASE_URL = "https://aihub.arcsysu.cn/v1",
           API_KEY = "sk-xxx",
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
            idx = end_brace + 1
            
            # Parse block content
            parsed_block = self._parse_block_content(config_body)
            block_configs[config_name] = ConfigNode(parsed_block)
        
        # 2. 解析扁平格式 (不在 config 块内的 KEY = VALUE)
        # 移除所有 config 块，只保留块外的内容
        content_without_blocks = content
        for config_name in block_configs:
            # 简单地移除已解析的 config 块
            pattern = r'config\s+' + config_name + r'\s*\{[^}]*\}'
            content_without_blocks = re.sub(pattern, '', content_without_blocks)
        
        # 解析剩余的扁平赋值
        flat_configs = self._parse_flat_content(content_without_blocks)
        
        return block_configs, flat_configs
    
    def _parse_block_content(self, body: str) -> dict:
        """解析 config block 内的内容"""
        lines = body.split('\n')
        parsed_lines = []
        
        for line in lines:
            line = line.rstrip()
            if not line or line.strip().startswith('//'):
                continue
            
            # Replace key = ... with "key": ...
            line = re.sub(r'^(\s*)([a-zA-Z_][a-zA-Z0-9_]+)\s*=\s*(.*)', r'\1"\2": \3', line)
            
            # Handle nested dicts (MODEL_NAME = {...})
            if line.strip().endswith('{'):
                # 不添加逗号，这是嵌套 dict 的开始
                parsed_lines.append(line)
            elif not line.strip().endswith(',') and not line.strip().endswith('}'):
                line += ','
                parsed_lines.append(line)
            else:
                parsed_lines.append(line)
        
        code_str = "tmp_dict = {\n" + "\n".join(parsed_lines) + "\n}"
        
        try:
            local_env = {}
            exec(code_str, {}, local_env)
            return local_env.get("tmp_dict", {})
        except Exception as e:
            print(f"[Secrets Parser Error] block parsing failed: {e}")
            print(f"Code string was:\n{code_str}")
            return {}
    
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
                
                # Try to parse the value
                try:
                    # Try as Python literal (string, number, dict, etc.)
                    value = ast.literal_eval(value_str)
                except (ValueError, SyntaxError):
                    # Fallback to raw string
                    value = value_str
                
                flat[key] = value
        
        return flat

    def _load_secrets(self):
        """加载 secrets.nxs 文件"""
        # 寻找当前执行目录下的 secrets.nxs
        secrets_file = pathlib.Path.cwd() / "secrets.nxs"
        
        # 如果当前目录没有，尝试项目根目录
        if not secrets_file.exists():
            # 尝试向上查找
            parent = pathlib.Path.cwd().parent
            secrets_file = parent / "secrets.nxs"
        
        if secrets_file.exists():
            with open(secrets_file, "r", encoding="utf-8") as f:
                content = f.read()
            self._block_configs, self._flat_configs = self._parse_nxs(content)
            
            # Debug output (can be removed in production)
            if os.environ.get("NEXA_DEBUG"):
                print(f"[Secrets] Loaded from: {secrets_file}")
                print(f"[Secrets] Block configs: {list(self._block_configs.keys())}")
                print(f"[Secrets] Flat configs: {list(self._flat_configs.keys())}")

    def __getattr__(self, name):
        """访问 config block"""
        if name in self._block_configs:
            return self._block_configs[name]
        return ConfigNode()

    def get(self, key: str, default: str = "") -> str:
        """
        获取配置值，按以下优先级查找:
        1. default config block 中的值
        2. 扁平格式中的值
        3. 环境变量
        
        Args:
            key: 配置键名 (如 API_KEY, BASE_URL, OPENAI_API_KEY)
            default: 默认值
            
        Returns:
            配置值字符串
        """
        # 1. 先查 default config block
        if "default" in self._block_configs:
            val = self._block_configs["default"].get(key)
            if val and not isinstance(val, ConfigNode):
                return str(val)
            elif val and isinstance(val, ConfigNode):
                # 如果是嵌套 ConfigNode，返回空字符串（需要用属性访问）
                return default
        
        # 2. 再查 flat configs
        if key in self._flat_configs:
            val = self._flat_configs[key]
            if not isinstance(val, dict):
                return str(val)
        
        # 3. 最后查环境变量
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
        
        # 从 default config block 获取
        if "default" in self._block_configs:
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
        # 1. 先查 provider 特定的 config block
        if provider in self._block_configs:
            block = self._block_configs[provider]
            api_key = block.get("API_KEY", "")
            base_url = block.get("BASE_URL", "")
            return api_key, base_url
        
        # 2. 查 provider 特定的环境变量格式
        api_key = self.get(f"{provider.upper()}_API_KEY")
        base_url = self.get(f"{provider.upper()}_BASE_URL")
        
        if api_key or base_url:
            return api_key, base_url
        
        # 3. Fallback 到 default config
        return self.get("API_KEY"), self.get("BASE_URL")

# 单例实例
nexa_secrets = NexaSecrets()