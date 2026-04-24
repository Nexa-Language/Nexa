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
IAL Vocabulary — 术语存储和模式匹配引擎

Glossary 定义领域术语映射（如 "they see X" → "body contains X"）。
Vocabulary 是 IAL 的核心：新断言是词汇条目，不需要改代码。

术语条目类型:
- pattern: 模式字符串，支持 {param} 占位符
- expansion: 展开为多个术语/原语（递归重写）
- primitive: 直接映射到 IAL 原语
- call: 调用 Nexa agent 做单元测试
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, Union, Callable

from src.ial.primitives import (
    Check, CheckOp, AgentAssertion, ProtocolCheck, PipelineCheck,
    SemanticCheck, Http, Primitive
)


@dataclass
class TermEntry:
    """
    Glossary 术语条目
    
    Types:
        - "expansion": 展开为多个术语字符串（递归重写）
        - "primitive": 直接映射到 IAL 原语实例
        - "call": 调用函数或 agent（动态映射）
        - "composite": 同时包含 pattern 和 expansion
    """
    term: str          # 术语模式（如 "they see {text}"）
    means: Any          # 展开目标（字符串列表 / 原语 / 函数）
    entry_type: str     # "expansion" | "primitive" | "call" | "composite"
    params: List[str] = field(default_factory=list)  # 从 pattern 提取的参数名
    description: str = ""
    
    def __repr__(self):
        return f"TermEntry({self.term!r} → {self.means!r}, type={self.entry_type})"


class Vocabulary:
    """
    IAL 术语词汇表 — 存储术语条目并提供模式匹配
    
    核心职责:
    1. 注册术语条目 (pattern → expansion/primitive/call)
    2. 模式匹配：将输入断言字符串匹配到术语条目
    3. 参数提取：从模式匹配中提取 {param} 值
    """
    
    def __init__(self):
        self._entries: Dict[str, TermEntry] = {}   # term → TermEntry (精确匹配)
        self._patterns: List[TermEntry] = []        # 含 {param} 的模式条目（模糊匹配）
        self._compiled_patterns: List[tuple] = []   # (compiled_regex, param_names, TermEntry)
    
    def register(self, term: str, means: Any, entry_type: str = "expansion",
                 description: str = ""):
        """
        注册术语条目
        
        Args:
            term: 术语模式，如 "they see {text}" 或精确术语 "response is valid"
            means: 展开目标
            entry_type: 条目类型 ("expansion" / "primitive" / "call" / "composite")
            description: 可选描述
        """
        # 提取参数名
        params = re.findall(r'\{(\w+)\}', term)
        
        entry = TermEntry(
            term=term,
            means=means,
            entry_type=entry_type,
            params=params,
            description=description
        )
        
        if params:
            # 含参数的模式 → 模糊匹配
            self._patterns.append(entry)
            # 编译正则：将 {param} 替换为捕获组
            pattern_regex = self._term_to_regex(term, params)
            compiled = re.compile(pattern_regex, re.IGNORECASE)
            self._compiled_patterns.append((compiled, params, entry))
        else:
            # 精确匹配
            self._entries[term.lower()] = entry
    
    def lookup(self, assertion_text: str) -> Optional[tuple]:
        """
        查找断言文本对应的术语条目
        
        Args:
            assertion_text: 断言文本，如 "they see success response"
        
        Returns:
            (TermEntry, extracted_params) 或 None
        """
        # 1. 先尝试精确匹配
        exact_match = self._entries.get(assertion_text.lower())
        if exact_match:
            return (exact_match, {})
        
        # 2. 再尝试模式匹配
        for compiled, param_names, entry in self._compiled_patterns:
            match = compiled.match(assertion_text.strip())
            if match:
                extracted = {}
                for i, param_name in enumerate(param_names):
                    extracted[param_name] = match.group(i + 1)
                return (entry, extracted)
        
        return None
    
    def _term_to_regex(self, term: str, params: List[str]) -> str:
        """
        将术语模式转换为正则表达式
        
        "they see {text}" → "^they see (.+?)$"
        "a user asks {question}" → "^a user asks (.+?)$"
        
        使用非贪婪匹配 (.+?) 以支持后续术语重写
        """
        regex = term
        for param in params:
            regex = regex.replace(f'{{{param}}}', f'(.+?)')
        # 转义特殊字符（除了我们的捕获组）
        # 先处理捕获组占位符之外的字符
        regex_escaped = ""
        i = 0
        while i < len(regex):
            if regex[i] == '(' and i + 1 < len(regex) and regex[i:i+5] == '(.+?)':
                regex_escaped += '(.+?)'
                i += 5
            else:
                regex_escaped += re.escape(regex[i])
                i += 1
        return f'^{regex_escaped}$'
    
    def expand_with_params(self, entry: TermEntry, params: Dict[str, str]) -> List[str]:
        """
        用提取的参数值展开术语条目的 means
        
        Args:
            entry: 术语条目
            params: 提取的参数值
        
        Returns:
            展开后的术语字符串列表
        """
        if entry.entry_type == "primitive":
            # 原语类型，不需要展开为字符串
            return []
        
        if entry.entry_type == "call":
            # 调用类型，不需要展开为字符串
            return []
        
        means = entry.means
        
        if isinstance(means, str):
            # 单个展开字符串 — 替换参数
            result = means
            for param_name, param_value in params.items():
                result = result.replace(f'{{{param_name}}}', param_value)
            return [result]
        
        if isinstance(means, list):
            # 多个展开字符串 — 替换每个中的参数
            results = []
            for item in means:
                if isinstance(item, str):
                    result = item
                    for param_name, param_value in params.items():
                        result = result.replace(f'{{{param_name}}}', param_value)
                    results.append(result)
                else:
                    results.append(item)
            return results
        
        return []
    
    def all_terms(self) -> List[TermEntry]:
        """返回所有已注册的术语条目"""
        return list(self._entries.values()) + self._patterns
    
    def term_count(self) -> int:
        """返回已注册术语数量"""
        return len(self._entries) + len(self._patterns)
    
    def __repr__(self):
        return f"Vocabulary({self.term_count()} terms: {len(self._entries)} exact, {len(self._patterns)} patterns)"