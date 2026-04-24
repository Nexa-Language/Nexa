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
Nexa 上下文压缩器 (Context Compactor)
在不丢失关键信息的前提下压缩对话历史，提升模型处理长上下文的能力
"""

import json
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from openai import OpenAI
from .secrets import nexa_secrets


@dataclass
class CompactionResult:
    """压缩结果"""
    original_messages: List[Dict]
    compressed_messages: List[Dict]
    summary: str
    original_token_estimate: int
    compressed_token_estimate: int
    compression_ratio: float
    key_entities: List[str] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)


class ContextCompactor:
    """
    上下文压缩器
    
    特性：
    - 智能摘要：保留关键信息，去除冗余
    - 实体提取：识别并保留重要实体
    - 决策追踪：记录重要决策和结论
    - 渐进式压缩：根据上下文长度选择压缩策略
    """
    
    DEFAULT_COMPACTOR_MODEL = "gpt-4o-mini"  # 轻量模型用于压缩
    
    # 压缩提示模板
    SUMMARIZE_PROMPT = """You are a context compression specialist. Your task is to summarize the following conversation history while preserving ALL critical information.

CRITICAL INFORMATION TO PRESERVE:
1. User's core requests and goals
2. Important facts, numbers, and data mentioned
3. Decisions made and conclusions reached
4. Key entities (names, places, products, etc.)
5. Action items and pending tasks
6. Any constraints or preferences stated by the user

OUTPUT FORMAT:
Return a JSON object with the following structure:
{
    "summary": "A concise summary of the conversation (2-3 sentences)",
    "key_entities": ["entity1", "entity2", ...],
    "key_decisions": ["decision1", "decision2", ...],
    "important_numbers": ["number1", "number2", ...],
    "pending_actions": ["action1", "action2", ...],
    "user_preferences": ["preference1", "preference2", ...]
}

CONVERSATION TO COMPRESS:
{conversation}
"""

    PROGRESSIVE_COMPACT_PROMPT = """Compress this conversation segment into a brief summary (1-2 sentences) that captures the essential information:

Segment: {segment}

Summary:"""

    def __init__(
        self,
        model: str = None,
        provider: str = "default",
        max_context_tokens: int = 4000,
        target_compression_ratio: float = 0.3
    ):
        self.model = model or self.DEFAULT_COMPACTOR_MODEL
        self.provider = provider
        self.max_context_tokens = max_context_tokens
        self.target_compression_ratio = target_compression_ratio
        
        # 初始化客户端
        api_key = nexa_secrets.get(f"{provider.upper()}_API_KEY")
        base_url = nexa_secrets.get(f"{provider.upper()}_BASE_URL")
        
        if not api_key:
            api_key = nexa_secrets.get("OPENAI_API_KEY", "sk-lDc9yRMvfPzpxXKuuXB2LA")
        if not base_url:
            base_url = "https://api.openai.com/v1"
            
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        
    def estimate_tokens(self, messages: List[Dict]) -> int:
        """估算消息的token数量（简化版）"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            # 粗略估算：每4个字符约1个token
            total += len(str(content)) // 4 + 10  # +10 for role overhead
        return total
    
    def compact(
        self,
        messages: List[Dict],
        preserve_recent: int = 2,
        strategy: str = "auto"
    ) -> CompactionResult:
        """
        压缩对话历史
        
        Args:
            messages: 消息列表
            preserve_recent: 保留最近的N轮对话不压缩
            strategy: 压缩策略 (auto, aggressive, conservative)
            
        Returns:
            CompactionResult: 压缩结果
        """
        if not messages:
            return CompactionResult(
                original_messages=[],
                compressed_messages=[],
                summary="",
                original_token_estimate=0,
                compressed_token_estimate=0,
                compression_ratio=1.0
            )
            
        original_tokens = self.estimate_tokens(messages)
        
        # 如果上下文不超限，直接返回
        if original_tokens < self.max_context_tokens * 0.7:
            return CompactionResult(
                original_messages=messages,
                compressed_messages=messages,
                summary="No compression needed",
                original_token_estimate=original_tokens,
                compressed_token_estimate=original_tokens,
                compression_ratio=1.0
            )
        
        # 分离系统消息和保留的最近对话
        system_msgs = [m for m in messages if m.get("role") == "system"]
        user_assistant_msgs = [m for m in messages if m.get("role") in ("user", "assistant")]
        
        # 保留最近的对话
        recent_msgs = user_assistant_msgs[-preserve_recent * 2:] if len(user_assistant_msgs) > preserve_recent * 2 else user_assistant_msgs
        to_compress = user_assistant_msgs[:-preserve_recent * 2] if len(user_assistant_msgs) > preserve_recent * 2 else []
        
        if not to_compress:
            return CompactionResult(
                original_messages=messages,
                compressed_messages=messages,
                summary="Nothing to compress",
                original_token_estimate=original_tokens,
                compressed_token_estimate=original_tokens,
                compression_ratio=1.0
            )
        
        # 选择压缩策略
        if strategy == "auto":
            if original_tokens > self.max_context_tokens * 1.5:
                strategy = "aggressive"
            else:
                strategy = "conservative"
        
        # 执行压缩
        if strategy == "aggressive":
            summary_result = self._aggressive_compress(to_compress)
        else:
            summary_result = self._progressive_compress(to_compress)
        
        # 构建压缩后的消息列表
        compressed_messages = system_msgs.copy()
        
        if summary_result.get("summary"):
            compressed_messages.append({
                "role": "system",
                "content": f"[Conversation Summary]: {summary_result['summary']}"
            })
            
            # 添加关键信息摘要
            key_info = []
            if summary_result.get("key_entities"):
                key_info.append(f"Key Entities: {', '.join(summary_result['key_entities'][:5])}")
            if summary_result.get("key_decisions"):
                key_info.append(f"Key Decisions: {', '.join(summary_result['key_decisions'][:3])}")
            if summary_result.get("pending_actions"):
                key_info.append(f"Pending: {', '.join(summary_result['pending_actions'][:3])}")
                
            if key_info:
                compressed_messages.append({
                    "role": "system",
                    "content": "[Key Information]: " + " | ".join(key_info)
                })
        
        compressed_messages.extend(recent_msgs)
        compressed_tokens = self.estimate_tokens(compressed_messages)
        
        return CompactionResult(
            original_messages=messages,
            compressed_messages=compressed_messages,
            summary=summary_result.get("summary", ""),
            original_token_estimate=original_tokens,
            compressed_token_estimate=compressed_tokens,
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            key_entities=summary_result.get("key_entities", []),
            key_decisions=summary_result.get("key_decisions", [])
        )
    
    def _aggressive_compress(self, messages: List[Dict]) -> Dict:
        """激进压缩：使用LLM生成摘要"""
        try:
            conversation_text = json.dumps(messages, ensure_ascii=False, indent=2)
            prompt = self.SUMMARIZE_PROMPT.format(conversation=conversation_text)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            return json.loads(result_text)
            
        except Exception as e:
            print(f"[Compactor] Aggressive compression failed: {e}")
            # 回退到简单摘要
            return {
                "summary": self._simple_summarize(messages),
                "key_entities": [],
                "key_decisions": []
            }
    
    def _progressive_compress(self, messages: List[Dict]) -> Dict:
        """渐进式压缩：分段压缩"""
        chunks = self._chunk_messages(messages, chunk_size=6)
        summaries = []
        all_entities = []
        all_decisions = []
        
        for chunk in chunks:
            try:
                chunk_text = json.dumps(chunk, ensure_ascii=False)
                prompt = self.PROGRESSIVE_COMPACT_PROMPT.format(segment=chunk_text)
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100
                )
                
                summary = response.choices[0].message.content.strip()
                summaries.append(summary)
                
            except Exception as e:
                print(f"[Compactor] Progressive chunk failed: {e}")
                summaries.append(self._simple_summarize(chunk))
        
        # 合并摘要
        if len(summaries) > 1:
            final_summary = self._merge_summaries(summaries)
        else:
            final_summary = summaries[0] if summaries else ""
        
        return {
            "summary": final_summary,
            "key_entities": all_entities,
            "key_decisions": all_decisions
        }
    
    def _chunk_messages(self, messages: List[Dict], chunk_size: int = 6) -> List[List[Dict]]:
        """将消息分割成块"""
        chunks = []
        for i in range(0, len(messages), chunk_size):
            chunks.append(messages[i:i + chunk_size])
        return chunks
    
    def _simple_summarize(self, messages: List[Dict]) -> str:
        """简单摘要：提取关键词"""
        keywords = []
        for msg in messages:
            content = msg.get("content", "")
            # 提取可能的实体和关键词
            words = re.findall(r'\b[A-Z][a-z]+\b|\b\d+(?:\.\d+)?%?\b', content)
            keywords.extend(words[:3])
        
        unique_keywords = list(set(keywords))[:5]
        return f"Discussion covered: {', '.join(unique_keywords) if unique_keywords else 'various topics'}"
    
    def _merge_summaries(self, summaries: List[str]) -> str:
        """合并多个摘要"""
        try:
            merge_prompt = f"Combine these summaries into one coherent paragraph:\n\n" + "\n".join(f"- {s}" for s in summaries)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": merge_prompt}],
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"[Compactor] Summary merge failed: {e}")
            return " ".join(summaries)


class CompactionPolicy:
    """压缩策略管理"""
    
    def __init__(
        self,
        trigger_threshold: float = 0.8,  # 上下文达到阈值时触发压缩
        preserve_ratio: float = 0.2,     # 保留最近对话的比例
        max_age_turns: int = 10          # 超过此轮数的对话将被压缩
    ):
        self.trigger_threshold = trigger_threshold
        self.preserve_ratio = preserve_ratio
        self.max_age_turns = max_age_turns
        
    def should_compact(self, current_tokens: int, max_tokens: int) -> bool:
        """判断是否需要压缩"""
        return current_tokens > max_tokens * self.trigger_threshold
    
    def get_compaction_params(self, total_messages: int) -> Dict:
        """获取压缩参数"""
        preserve_count = max(2, int(total_messages * self.preserve_ratio))
        return {
            "preserve_recent": preserve_count,
            "strategy": "conservative" if total_messages < 20 else "aggressive"
        }


# 全局压缩器实例
_global_compactor: Optional[ContextCompactor] = None


def get_compactor() -> ContextCompactor:
    """获取全局压缩器实例"""
    global _global_compactor
    if _global_compactor is None:
        _global_compactor = ContextCompactor()
    return _global_compactor


def compact_context(messages: List[Dict], **kwargs) -> CompactionResult:
    """便捷函数：压缩上下文"""
    return get_compactor().compact(messages, **kwargs)


__all__ = [
    'ContextCompactor', 'CompactionResult', 'CompactionPolicy',
    'get_compactor', 'compact_context'
]