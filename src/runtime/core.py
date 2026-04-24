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

from .secrets import nexa_secrets

# 动态获取配置
_base_url = nexa_secrets.get("BASE_URL") or nexa_secrets.get("OPENAI_API_BASE")
_api_key = nexa_secrets.get("API_KEY") or nexa_secrets.get("OPENAI_API_KEY")

# 如果没有配置，使用默认值
if not _base_url:
    _base_url = "https://aihub.arcsysu.cn/v1"  # 默认使用 aihub

if not _api_key:
    # 在开发阶段，如果没有配置，给出警告而不是报错
    print("[Warning] API key not configured. Please create secrets.nxs with API_KEY or OPENAI_API_KEY.")
    print("[Warning] Using fallback configuration for development.")
    _api_key = os.environ.get("NEXA_DEV_API_KEY", "")

client = OpenAI(
    base_url=_base_url,
    api_key=_api_key
)

# 从 secrets 获取模型配置
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