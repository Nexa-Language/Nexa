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

from openai import OpenAI
import os
from threading import Lock
from typing import Any

from .secrets import DEFAULT_OPENAI_COMPATIBLE_BASE_URL, nexa_secrets

class LazyClient:
    """Resolve credentials only when an evaluation actually needs a provider."""

    def __init__(self) -> None:
        self._client: OpenAI | None = None
        self._lock = Lock()
        self._configuration: tuple[str, str] | None = None

    def __getattr__(self, name: str) -> Any:
        base_url = nexa_secrets.get("BASE_URL") or DEFAULT_OPENAI_COMPATIBLE_BASE_URL
        api_key = nexa_secrets.get("API_KEY") or os.environ.get("NEXA_DEV_API_KEY", "")
        if not api_key:
            raise RuntimeError("Provider credentials are required for model evaluation; configure API_KEY before execution")
        with self._lock:
            if self._client is None or self._configuration != (base_url, api_key):
                previous = self._client
                self._client = OpenAI(base_url=base_url, api_key=api_key)
                self._configuration = (base_url, api_key)
                if previous is not None:
                    previous.close()
            return getattr(self._client, name)


client = LazyClient()

# 从 secrets 获取模型配置（动态函数，支持 config 切换）
def _get_model_config():
    """获取当前激活 config 的模型配置"""
    return nexa_secrets.get_model_config()

def get_strong_model() -> str:
    """获取 strong 模型名称"""
    return _get_model_config().get("strong", "minimax-m2.5")

def get_weak_model() -> str:
    """获取 weak 模型名称"""
    return _get_model_config().get("weak", "deepseek-chat")

# 向后兼容：模块级常量（在导入时求值）
_model_config = nexa_secrets.get_model_config()
STRONG_MODEL = _model_config.get("strong", "minimax-m2.5")
WEAK_MODEL = _model_config.get("weak", "deepseek-chat")


import base64
import mimetypes

def nexa_fallback(primary_fn, backup_fn):
    try:
        return primary_fn()
    except Exception as e:
        print(f"[Fallback Triggered] Primary failed with: {e}")
        return backup_fn()

def nexa_img_loader(filepath):
    try:
        mime_type, _ = mimetypes.guess_type(filepath)
        if mime_type is None:
            mime_type = "image/jpeg"
        with open(filepath, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{encoded}"}
        }
    except Exception as e:
        print(f"[Image Load Error]: {e}")
        return str(filepath)  # fallback to just returning the path if load fails
