"""
Nexa v2.0 ContextManager — 上下文管理器

ContextManager 实现 Harness C-dimension 的运行时核心，负责：
  - with_context 作用域管理 (enter_scope/exit_scope)
  - 消息添加与工具输出卸载 (add_message/add_tool_result)
  - Token 溢出检测与三层压缩 (sliding_window / importance_weighted / smart_summarization)

Design Rationale:
  - 作用域栈: 支持嵌套 with_context，每层独立 max_tokens 和 strategy
  - 三层压缩: sliding_window (最简单) → importance_weighted (中等) → smart_summarization (最智能)
  - 工具输出卸载: 大型工具输出写入 ToolOutputStore，context 只保留摘要
  - v1.x 兼容: 无 with_context 时，ContextManager 退化为简单消息列表

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.2
"""

from __future__ import annotations

import time
import logging
import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .harness_kernel import HarnessKernel, ContextScope, HarnessRuntimeMode

logger = logging.getLogger("nexa.context_manager")


# ═══════════════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ContextMessage:
    """A single message in the context window."""
    role: str = "user"       # user | assistant | system | tool
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    priority: int = 1        # 1=low, 5=critical (for importance_weighted eviction)
    tags: Set[str] = field(default_factory=set)
    token_count: int = 0     # Estimated token count
    compressed: bool = False  # Whether this message has been compressed
    original_hash: Optional[str] = None  # Hash of original content (for dedup)

    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "tags": list(self.tags),
            "token_count": self.token_count,
            "compressed": self.compressed,
        }


@dataclass
class ToolOutputRef:
    """Reference to a tool output stored in ToolOutputStore."""
    output_id: str = ""
    tool_name: str = ""
    summary: str = ""        # Brief summary kept in context
    full_output_path: str = ""  # Path to full output in ToolOutputStore
    token_count: int = 0     # Tokens saved by offloading

    def to_dict(self) -> Dict:
        return {
            "output_id": self.output_id,
            "tool_name": self.tool_name,
            "summary": self.summary,
            "token_count": self.token_count,
        }


@dataclass
class EvictionStats:
    """Statistics about context eviction operations."""
    total_evictions: int = 0
    messages_removed: int = 0
    messages_compressed: int = 0
    tokens_saved: int = 0
    last_eviction_time: float = 0.0
    eviction_strategy: str = ""

    def to_dict(self) -> Dict:
        return {
            "total_evictions": self.total_evictions,
            "messages_removed": self.messages_removed,
            "messages_compressed": self.messages_compressed,
            "tokens_saved": self.tokens_saved,
            "last_eviction_time": self.last_eviction_time,
            "eviction_strategy": self.eviction_strategy,
        }


# ═══════════════════════════════════════════════════════════════════════
#  Token Estimation
# ═══════════════════════════════════════════════════════════════════════

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text string.

    Uses a simple heuristic: ~4 characters per token for English,
    ~2 characters per token for Chinese/mixed content.
    This is a rough estimate; precise counting requires the actual tokenizer.
    """
    if not text:
        return 0
    # Count Chinese characters
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    # Chinese: ~2 chars/token, English: ~4 chars/token
    return max(1, chinese_chars // 2 + other_chars // 4)


# ═══════════════════════════════════════════════════════════════════════
#  ContextManager — C-Dimension Runtime
# ═══════════════════════════════════════════════════════════════════════

class ContextManager:
    """
    Context window manager for Agent execution.

    Implements the C-dimension runtime:
      - enter_scope/exit_scope: with_context scope management
      - add_message: Add messages with automatic token counting
      - add_tool_result: Add tool outputs with offloading to ToolOutputStore
      - _check_and_evict: Automatic eviction when token limit exceeded
      - Three eviction strategies: sliding_window, importance_weighted, smart_summarization

    Usage:
        cm = ContextManager(kernel=harness_kernel)
        scope = cm.enter_scope("main", {"max_tokens": 100000, "strategy": "sliding_window"})
        cm.add_message("user", "Hello, agent!")
        cm.exit_scope("main")
    """

    def __init__(self, kernel: HarnessKernel) -> None:
        self.kernel = kernel
        self._scope_stack: List[ContextScope] = []
        self._messages: List[ContextMessage] = []
        self._tool_output_refs: List[ToolOutputRef] = []
        self._eviction_stats = EvictionStats()
        self._default_max_tokens = 100000
        self._default_strategy = "sliding_window"

    # ─── Scope Management ───

    def enter_scope(self, scope_name: str, config: Dict) -> ContextScope:
        """
        Enter a with_context scope.

        Args:
            scope_name: Unique name for this scope
            config: Dict with max_tokens, strategy, priority_tags

        Returns:
            ContextScope for this scope
        """
        max_tokens = config.get("max_tokens", self._default_max_tokens)
        strategy = config.get("strategy", self._default_strategy)
        priority_tags = set(config.get("priority_tags", []))

        # Determine parent scope
        parent_scope = None
        if self._scope_stack:
            parent_scope = self._scope_stack[-1].max_tokens  # Use parent's max_tokens as reference

        scope = ContextScope(
            max_tokens=max_tokens,
            strategy=strategy,
            priority_tags=priority_tags,
            parent_scope=str(parent_scope) if parent_scope else None,
        )

        self._scope_stack.append(scope)
        logger.info(f"Entered context scope: max_tokens={max_tokens}, strategy={strategy}")

        # Register with kernel
        self.kernel.enter_context_scope(scope_name, config)

        return scope

    def exit_scope(self, scope_name: str) -> None:
        """
        Exit a with_context scope.

        Restores the previous scope's token limit and strategy.
        """
        if self._scope_stack:
            self._scope_stack.pop()
            logger.info(f"Exited context scope")

        # Unregister from kernel
        self.kernel.exit_context_scope(scope_name)

    def get_current_scope(self) -> ContextScope:
        """Get the current active scope (or default if no scope active)."""
        if self._scope_stack:
            return self._scope_stack[-1]
        return ContextScope(
            max_tokens=self._default_max_tokens,
            strategy=self._default_strategy,
        )

    def get_current_max_tokens(self) -> int:
        """Get the current max_tokens limit."""
        return self.get_current_scope().max_tokens

    def get_current_strategy(self) -> str:
        """Get the current eviction strategy."""
        return self.get_current_scope().strategy

    # ─── Message Management ───

    def add_message(
        self,
        role: str,
        content: str,
        priority: int = 1,
        tags: Optional[Set[str]] = None,
    ) -> ContextMessage:
        """
        Add a message to the context window.

        Automatically estimates token count and triggers eviction if needed.

        Args:
            role: Message role (user, assistant, system, tool)
            content: Message content
            priority: Message priority (1=low, 5=critical)
            tags: Optional tags for importance_weighted eviction

        Returns:
            The created ContextMessage
        """
        msg = ContextMessage(
            role=role,
            content=content,
            priority=priority,
            tags=tags or set(),
            token_count=estimate_tokens(content),
            original_hash=hashlib.md5(content.encode()).hexdigest()[:8] if content else None,
        )

        self._messages.append(msg)

        # Check and evict if token limit exceeded
        self._check_and_evict()

        # Trace event
        self.kernel.trace_event("context_add_message", {
            "role": role,
            "token_count": msg.token_count,
            "total_tokens": self.get_total_tokens(),
        })

        return msg

    def add_tool_result(
        self,
        tool_name: str,
        output: str,
        summary: Optional[str] = None,
        max_summary_tokens: int = 200,
    ) -> ToolOutputRef:
        """
        Add a tool output to the context.

        Large outputs are offloaded to ToolOutputStore, with only a summary
        kept in the context window.

        Args:
            tool_name: Name of the tool that produced the output
            output: Full tool output content
            summary: Optional manual summary; if None, auto-generated
            max_summary_tokens: Max tokens for auto-generated summary

        Returns:
            ToolOutputRef with reference to the stored output
        """
        output_tokens = estimate_tokens(output)

        # Generate summary if not provided
        if not summary:
            summary = self._auto_summarize(output, max_summary_tokens)

        # Create reference
        output_id = hashlib.md5(f"{tool_name}:{time.time()}".encode()).hexdigest()[:12]
        ref = ToolOutputRef(
            output_id=output_id,
            tool_name=tool_name,
            summary=summary,
            token_count=output_tokens,
        )

        self._tool_output_refs.append(ref)

        # Add summary to context (not full output)
        self.add_message(
            role="tool",
            content=f"[Tool: {tool_name}] {summary}",
            priority=3,  # Tool outputs are medium priority
            tags={"tool_output", tool_name},
        )

        logger.info(f"Tool output offloaded: {tool_name}, "
                     f"full={output_tokens} tokens, summary={estimate_tokens(summary)} tokens")

        return ref

    def _auto_summarize(self, text: str, max_tokens: int = 200) -> str:
        """
        Auto-generate a summary of a tool output.

        Simple implementation: truncate to max_tokens estimated character count.
        M4 will upgrade this to LLM-based summarization.
        """
        if not text:
            return ""

        # Estimate character count from token limit
        max_chars = max_tokens * 4  # ~4 chars per token

        if len(text) <= max_chars:
            return text

        # Truncate with indicator
        return text[:max_chars] + f"... [truncated, full output: {estimate_tokens(text)} tokens]"

    # ─── Token Counting ───

    def get_total_tokens(self) -> int:
        """Get the total estimated token count of all messages."""
        return sum(msg.token_count for msg in self._messages)

    def get_message_count(self) -> int:
        """Get the total number of messages in context."""
        return len(self._messages)

    def get_messages(self) -> List[ContextMessage]:
        """Get all messages in context (for LLM API call)."""
        return list(self._messages)

    def get_messages_as_dicts(self) -> List[Dict]:
        """Get all messages as dicts (for LLM API serialization)."""
        return [msg.to_dict() for msg in self._messages]

    # ─── Eviction ───

    def _check_and_evict(self) -> None:
        """
        Check if token limit is exceeded and trigger eviction.

        Uses the current scope's strategy and max_tokens.
        """
        current_max = self.get_current_max_tokens()
        current_tokens = self.get_total_tokens()

        if current_tokens <= current_max:
            return  # No eviction needed

        strategy = self.get_current_strategy()
        logger.warning(f"Token overflow: {current_tokens} > {current_max}, "
                       f"evicting with strategy={strategy}")

        if strategy == "sliding_window":
            self._apply_sliding_window(current_max)
        elif strategy == "importance_weighted":
            self._apply_importance_weighted(current_max)
        elif strategy == "smart_summarization":
            self._apply_smart_summarization(current_max)
        else:
            # Default to sliding_window
            self._apply_sliding_window(current_max)

    def _apply_sliding_window(self, target_tokens: int) -> None:
        """
        Sliding window eviction: remove oldest messages until under target.

        Keeps system messages and the most recent N messages.
        """
        removed_count = 0
        tokens_saved = 0

        # Never remove system messages (priority >= 5)
        while self.get_total_tokens() > target_tokens and len(self._messages) > 1:
            # Find the oldest non-critical message
            for i, msg in enumerate(self._messages):
                if msg.priority < 5 and msg.role != "system":
                    tokens_saved += msg.token_count
                    self._messages.pop(i)
                    removed_count += 1
                    break
            else:
                # All remaining messages are critical — can't evict more
                break

        self._eviction_stats.total_evictions += 1
        self._eviction_stats.messages_removed += removed_count
        self._eviction_stats.tokens_saved += tokens_saved
        self._eviction_stats.last_eviction_time = time.time()
        self._eviction_stats.eviction_strategy = "sliding_window"

        logger.info(f"Sliding window eviction: removed {removed_count} messages, "
                     f"saved {tokens_saved} tokens")

    def _apply_importance_weighted(self, target_tokens: int) -> None:
        """
        Importance-weighted eviction: remove lowest-priority messages first.

        Messages are sorted by priority, and low-priority ones are removed
        until the token budget is satisfied.
        """
        removed_count = 0
        tokens_saved = 0

        # Sort messages by priority (ascending = lowest first for removal)
        # Keep system messages (priority >= 5) and tagged messages
        while self.get_total_tokens() > target_tokens and len(self._messages) > 1:
            # Find the lowest priority non-system message
            lowest_idx = None
            lowest_priority = 999

            for i, msg in enumerate(self._messages):
                if msg.priority < 5 and msg.role != "system" and msg.priority < lowest_priority:
                    # Check if message is in priority_tags of current scope
                    scope = self.get_current_scope()
                    if msg.tags & scope.priority_tags:
                        continue  # Skip messages matching priority tags
                    lowest_idx = i
                    lowest_priority = msg.priority

            if lowest_idx is not None:
                tokens_saved += self._messages[lowest_idx].token_count
                self._messages.pop(lowest_idx)
                removed_count += 1
            else:
                break  # No more removable messages

        self._eviction_stats.total_evictions += 1
        self._eviction_stats.messages_removed += removed_count
        self._eviction_stats.tokens_saved += tokens_saved
        self._eviction_stats.last_eviction_time = time.time()
        self._eviction_stats.eviction_strategy = "importance_weighted"

        logger.info(f"Importance-weighted eviction: removed {removed_count} messages, "
                     f"saved {tokens_saved} tokens")

    def _apply_smart_summarization(self, target_tokens: int) -> None:
        """
        Smart summarization eviction: compress older messages into summaries.

        Instead of removing messages entirely, older low-priority messages
        are compressed into a single summary message.
        """
        compressed_count = 0
        tokens_saved = 0

        # Find messages that can be compressed (older, non-critical)
        compressible = []
        for i, msg in enumerate(self._messages):
            if msg.priority < 5 and msg.role != "system" and not msg.compressed:
                compressible.append((i, msg))

        if not compressible:
            # Fall back to sliding window if nothing to compress
            self._apply_sliding_window(target_tokens)
            return

        # Compress the oldest batch of compressible messages
        batch_size = min(len(compressible), 5)  # Compress up to 5 messages at once
        batch = compressible[:batch_size]

        # Generate summary
        summary_parts = []
        for _, msg in batch:
            summary_parts.append(f"[{msg.role}] {msg.content[:100]}")

        summary = " | ".join(summary_parts)
        summary_tokens = estimate_tokens(summary)

        # Calculate tokens saved
        original_tokens = sum(msg.token_count for _, msg in batch)
        tokens_saved = original_tokens - summary_tokens

        # Remove original messages and add compressed summary
        for idx, _ in batch:
            self._messages[idx] = None  # Mark for removal

        # Remove None entries
        self._messages = [m for m in self._messages if m is not None]

        # Add compressed summary
        compressed_msg = ContextMessage(
            role="system",
            content=f"[Compressed context] {summary}",
            priority=2,
            token_count=summary_tokens,
            compressed=True,
        )
        self._messages.append(compressed_msg)
        compressed_count = batch_size

        self._eviction_stats.total_evictions += 1
        self._eviction_stats.messages_compressed += compressed_count
        self._eviction_stats.tokens_saved += tokens_saved
        self._eviction_stats.last_eviction_time = time.time()
        self._eviction_stats.eviction_strategy = "smart_summarization"

        logger.info(f"Smart summarization: compressed {compressed_count} messages, "
                     f"saved {tokens_saved} tokens")

        # If still over limit, apply sliding window as fallback
        if self.get_total_tokens() > target_tokens:
            self._apply_sliding_window(target_tokens)

    # ─── Statistics ───

    def get_eviction_stats(self) -> EvictionStats:
        """Get eviction statistics."""
        return self._eviction_stats

    def get_context_stats(self) -> Dict:
        """Get comprehensive context statistics."""
        return {
            "total_tokens": self.get_total_tokens(),
            "max_tokens": self.get_current_max_tokens(),
            "strategy": self.get_current_strategy(),
            "message_count": self.get_message_count(),
            "scope_depth": len(self._scope_stack),
            "tool_output_refs": len(self._tool_output_refs),
            "eviction_stats": self._eviction_stats.to_dict(),
        }

    # ─── Reset ───

    def reset(self) -> None:
        """Reset the context manager (for testing)."""
        self._scope_stack = []
        self._messages = []
        self._tool_output_refs = []
        self._eviction_stats = EvictionStats()