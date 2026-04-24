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
Nexa Reason Primitive - 上下文感知推理原语

提供类型感知的推理调用，根据返回类型自动约束模型输出。

Usage:
    # 根据类型自动约束输出
    float risk_score = reason("评估风险指数", context=data);
    dict risk_details = reason("评估风险详情", context=data);
    string risk_report = reason("生成风险报告", context=data);
"""

import json
from typing import Any, Type, TypeVar, get_type_hints
from pydantic import BaseModel

from .core import client, STRONG_MODEL
from .secrets import nexa_secrets
from openai import OpenAI

T = TypeVar('T')


class ReasonResult:
    """reason() 调用结果包装器"""
    
    def __init__(self, content: str, parsed: Any = None):
        self._content = content
        self._parsed = parsed
    
    def __str__(self) -> str:
        return self._content
    
    def __repr__(self) -> str:
        return f"ReasonResult({self._content[:50]}...)"
    
    @property
    def content(self) -> str:
        return self._content
    
    @property
    def parsed(self) -> Any:
        return self._parsed


def reason(
    prompt: str,
    context: Any = None,
    model: str = None,
    return_type: Type[T] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7
) -> T:
    """
    上下文感知推理原语
    
    根据返回类型自动约束模型输出格式。
    
    Args:
        prompt: 推理任务描述
        context: 上下文数据（可选）
        model: 使用的模型（可选，默认使用 STRONG_MODEL）
        return_type: 返回类型（可选，用于类型约束）
        max_tokens: 最大输出 token 数
        temperature: 模型温度
    
    Returns:
        根据类型约束返回相应类型的结果
    """
    # 获取模型配置
    provider = "default"
    model_name = model or STRONG_MODEL
    
    if "/" in model_name:
        provider, model_name = model_name.split("/", 1)
    
    # 获取 API 配置
    api_key, base_url = nexa_secrets.get_provider_config(provider)
    
    if not api_key:
        api_key = nexa_secrets.get("API_KEY") or nexa_secrets.get("OPENAI_API_KEY")
    if not base_url:
        base_url = nexa_secrets.get("BASE_URL") or nexa_secrets.get("OPENAI_API_BASE")
    
    # Provider-specific defaults
    if not base_url:
        if provider == "deepseek":
            base_url = "https://api.deepseek.com/v1"
        elif provider == "minimax":
            base_url = "https://aihub.arcsysu.cn/v1"
        elif provider == "openai":
            base_url = "https://api.openai.com/v1"
        else:
            base_url = "https://api.openai.com/v1"
    
    if not api_key:
        raise ValueError(f"API key not found for provider '{provider}'")
    
    # 创建客户端
    openai_client = OpenAI(api_key=api_key, base_url=base_url)
    
    # 构建消息
    messages = []
    
    # 根据返回类型添加格式约束
    type_instruction = ""
    if return_type is not None:
        type_name = getattr(return_type, '__name__', str(return_type))
        
        if return_type == float:
            type_instruction = "You MUST respond with ONLY a single floating-point number, nothing else."
        elif return_type == int:
            type_instruction = "You MUST respond with ONLY a single integer number, nothing else."
        elif return_type == str:
            type_instruction = "You MUST respond with a text string."
        elif return_type == bool:
            type_instruction = "You MUST respond with ONLY 'true' or 'false'."
        elif return_type == dict or (hasattr(return_type, '__origin__') and return_type.__origin__ == dict):
            type_instruction = "You MUST respond with a valid JSON object, nothing else."
        elif return_type == list or (hasattr(return_type, '__origin__') and return_type.__origin__ == list):
            type_instruction = "You MUST respond with a valid JSON array, nothing else."
        elif isinstance(return_type, type) and issubclass(return_type, BaseModel):
            # Pydantic 模型
            schema = return_type.model_json_schema()
            fields = list(schema.get('properties', {}).keys())
            type_instruction = f"You MUST respond with a valid JSON object containing these fields: {', '.join(fields)}. Do not include any text outside the JSON object."
    
    if type_instruction:
        messages.append({"role": "system", "content": type_instruction})
    
    # 构建用户消息
    user_message = prompt
    if context is not None:
        if isinstance(context, str):
            user_message += f"\n\nContext:\n{context}"
        elif isinstance(context, (dict, list)):
            user_message += f"\n\nContext:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
        else:
            user_message += f"\n\nContext:\n{str(context)}"
    
    messages.append({"role": "user", "content": user_message})
    
    # 调用模型
    kwargs = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    
    response = openai_client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    
    # 根据返回类型解析结果
    if return_type is None:
        return content
    
    try:
        if return_type == float:
            # 尝试提取数字
            import re
            numbers = re.findall(r'[-+]?\d*\.?\d+', content)
            if numbers:
                return float(numbers[0])
            return float(content.strip())
        
        elif return_type == int:
            import re
            numbers = re.findall(r'[-+]?\d+', content)
            if numbers:
                return int(numbers[0])
            return int(float(content.strip()))
        
        elif return_type == bool:
            lower_content = content.lower().strip()
            return lower_content in ('true', 'yes', '1', 'correct', 'right')
        
        elif return_type == str:
            return content.strip()
        
        elif return_type == dict:
            # 尝试解析 JSON
            # 移除可能的 markdown 代码块标记
            cleaned = content.strip()
            if cleaned.startswith('```'):
                lines = cleaned.split('\n')
                cleaned = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
            return json.loads(cleaned)
        
        elif return_type == list:
            cleaned = content.strip()
            if cleaned.startswith('```'):
                lines = cleaned.split('\n')
                cleaned = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
            return json.loads(cleaned)
        
        elif isinstance(return_type, type) and issubclass(return_type, BaseModel):
            # Pydantic 模型
            cleaned = content.strip()
            if cleaned.startswith('```'):
                lines = cleaned.split('\n')
                cleaned = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
            parsed = json.loads(cleaned)
            return return_type.model_validate(parsed)
        
        else:
            return content
            
    except Exception as e:
        print(f"[reason] Failed to parse result as {return_type}: {e}")
        print(f"[reason] Raw content: {content[:200]}")
        return content


def reason_float(prompt: str, context: Any = None, **kwargs) -> float:
    """便捷函数：返回 float 类型的推理结果"""
    return reason(prompt, context, return_type=float, **kwargs)


def reason_int(prompt: str, context: Any = None, **kwargs) -> int:
    """便捷函数：返回 int 类型的推理结果"""
    return reason(prompt, context, return_type=int, **kwargs)


def reason_bool(prompt: str, context: Any = None, **kwargs) -> bool:
    """便捷函数：返回 bool 类型的推理结果"""
    return reason(prompt, context, return_type=bool, **kwargs)


def reason_str(prompt: str, context: Any = None, **kwargs) -> str:
    """便捷函数：返回 str 类型的推理结果"""
    return reason(prompt, context, return_type=str, **kwargs)


def reason_dict(prompt: str, context: Any = None, **kwargs) -> dict:
    """便捷函数：返回 dict 类型的推理结果"""
    return reason(prompt, context, return_type=dict, **kwargs)


def reason_list(prompt: str, context: Any = None, **kwargs) -> list:
    """便捷函数：返回 list 类型的推理结果"""
    return reason(prompt, context, return_type=list, **kwargs)


def reason_model(model_class: Type[BaseModel], prompt: str, context: Any = None, **kwargs) -> BaseModel:
    """便捷函数：返回 Pydantic 模型类型的推理结果"""
    return reason(prompt, context, return_type=model_class, **kwargs)


__all__ = [
    'reason',
    'reason_float',
    'reason_int',
    'reason_bool',
    'reason_str',
    'reason_dict',
    'reason_list',
    'reason_model',
    'ReasonResult'
]