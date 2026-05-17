"""
Nexa v2.0 ToolOutputStore — 工具输出转储

ToolOutputStore 将大型工具输出从 context window 卸载到持久化存储，
只保留摘要引用在 context 中，防止 Token 溢出。

Design Rationale:
  - 文件存储: 大型输出写入临时文件，context 只保留摘要和引用
  - 内存缓存: 小型输出 (<1KB) 保留在内存中，避免不必要的文件 I/O
  - 自动清理: 超过 TTL 的输出自动清理，防止磁盘占用膨胀
  - 线程安全: 多 Agent 并行执行时安全访问

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.2
"""

from __future__ import annotations

import os
import json
import time
import hashlib
import tempfile
import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nexa.tool_output_store")


# ═══════════════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ToolOutputEntry:
    """A stored tool output entry."""
    output_id: str = ""
    tool_name: str = ""
    content: str = ""           # Full output content (for small outputs)
    file_path: Optional[str] = None  # Path to file (for large outputs)
    summary: str = ""           # Brief summary for context
    token_count: int = 0        # Estimated tokens in full output
    created_at: float = field(default_factory=time.time)
    ttl: int = 3600             # Time-to-live in seconds (default: 1 hour)
    size_bytes: int = 0         # Size of the output in bytes

    def to_dict(self) -> Dict:
        return {
            "output_id": self.output_id,
            "tool_name": self.tool_name,
            "summary": self.summary,
            "token_count": self.token_count,
            "created_at": self.created_at,
            "ttl": self.ttl,
            "size_bytes": self.size_bytes,
            "stored_in_file": self.file_path is not None,
        }


# ═══════════════════════════════════════════════════════════════════════
#  ToolOutputStore
# ═══════════════════════════════════════════════════════════════════════

class ToolOutputStore:
    """
    Persistent store for tool outputs, offloaded from context window.

    Implements:
      - store(): Save a tool output (small → memory, large → file)
      - retrieve(): Get a stored output by ID
      - get_summary(): Get just the summary (for context window)
      - cleanup(): Remove expired entries

    Usage:
        store = ToolOutputStore()
        ref = store.store("shell_exec", "large output...", summary="command succeeded")
        # In context: only ref.summary is kept
        # Full output: store.retrieve(ref.output_id)
    """

    # Threshold: outputs larger than this are written to files
    FILE_THRESHOLD_BYTES = 1024  # 1KB

    def __init__(self, base_dir: Optional[str] = None, default_ttl: int = 3600) -> None:
        self._base_dir = base_dir or tempfile.mkdtemp(prefix="nexa_tool_output_")
        self._default_ttl = default_ttl
        self._entries: Dict[str, ToolOutputEntry] = {}
        self._lock = threading.Lock()
        self._total_stored = 0
        self._total_retrieved = 0

        # Ensure base directory exists
        os.makedirs(self._base_dir, exist_ok=True)

    def store(
        self,
        tool_name: str,
        output: str,
        summary: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> ToolOutputEntry:
        """
        Store a tool output.

        Args:
            tool_name: Name of the tool that produced the output
            output: Full output content
            summary: Optional summary; auto-generated if None
            ttl: Time-to-live in seconds; uses default if None

        Returns:
            ToolOutputEntry with reference info
        """
        output_id = hashlib.md5(
            f"{tool_name}:{time.time()}:{self._total_stored}".encode()
        ).hexdigest()[:12]

        size_bytes = len(output.encode('utf-8')) if output else 0
        token_count = self._estimate_tokens(output)

        # Auto-generate summary if not provided
        if not summary:
            summary = self._auto_summarize(output)

        entry = ToolOutputEntry(
            output_id=output_id,
            tool_name=tool_name,
            content="",  # Will be set below
            summary=summary,
            token_count=token_count,
            created_at=time.time(),
            ttl=ttl or self._default_ttl,
            size_bytes=size_bytes,
        )

        # Decide storage strategy: small → memory, large → file
        if size_bytes > self.FILE_THRESHOLD_BYTES:
            # Write to file
            file_path = os.path.join(self._base_dir, f"{output_id}.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(output)
            entry.file_path = file_path
            entry.content = ""  # Don't keep in memory
            logger.info(f"Tool output stored in file: {output_id}, "
                         f"size={size_bytes} bytes, tokens={token_count}")
        else:
            # Keep in memory
            entry.content = output
            entry.file_path = None
            logger.info(f"Tool output stored in memory: {output_id}, "
                         f"size={size_bytes} bytes, tokens={token_count}")

        with self._lock:
            self._entries[output_id] = entry
            self._total_stored += 1

        return entry

    def retrieve(self, output_id: str) -> Optional[str]:
        """
        Retrieve a stored tool output by ID.

        Returns:
            The full output content, or None if not found/expired
        """
        with self._lock:
            entry = self._entries.get(output_id)
            if not entry:
                logger.warning(f"Tool output not found: {output_id}")
                return None

            # Check TTL
            if time.time() - entry.created_at > entry.ttl:
                self._cleanup_entry(output_id)
                logger.warning(f"Tool output expired: {output_id}")
                return None

            self._total_retrieved += 1

        # Retrieve from memory or file
        if entry.content:
            return entry.content

        if entry.file_path and os.path.exists(entry.file_path):
            with open(entry.file_path, 'r', encoding='utf-8') as f:
                return f.read()

        logger.warning(f"Tool output file missing: {output_id}")
        return None

    def get_summary(self, output_id: str) -> Optional[str]:
        """
        Get just the summary of a stored output (for context window).

        Returns:
            The summary string, or None if not found
        """
        with self._lock:
            entry = self._entries.get(output_id)
            if not entry:
                return None
            return entry.summary

    def get_entry(self, output_id: str) -> Optional[ToolOutputEntry]:
        """Get the full entry metadata."""
        with self._lock:
            return self._entries.get(output_id)

    def cleanup(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        removed = 0
        now = time.time()

        with self._lock:
            expired_ids = [
                id for id, entry in self._entries.items()
                if now - entry.created_at > entry.ttl
            ]

        for output_id in expired_ids:
            self._cleanup_entry(output_id)
            removed += 1

        logger.info(f"Tool output cleanup: removed {removed} expired entries")
        return removed

    def _cleanup_entry(self, output_id: str) -> None:
        """Remove a single entry and its file."""
        with self._lock:
            entry = self._entries.pop(output_id, None)

        if entry and entry.file_path and os.path.exists(entry.file_path):
            try:
                os.remove(entry.file_path)
            except OSError:
                pass

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string."""
        if not text:
            return 0
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return max(1, chinese_chars // 2 + other_chars // 4)

    def _auto_summarize(self, text: str, max_chars: int = 400) -> str:
        """Auto-generate a brief summary."""
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."

    # ─── Statistics ───

    def get_stats(self) -> Dict:
        """Get store statistics."""
        with self._lock:
            total_entries = len(self._entries)
            total_bytes = sum(e.size_bytes for e in self._entries.values())
            in_memory = sum(1 for e in self._entries.values() if e.file_path is None)
            in_file = sum(1 for e in self._entries.values() if e.file_path is not None)

        return {
            "total_entries": total_entries,
            "total_bytes": total_bytes,
            "in_memory": in_memory,
            "in_file": in_file,
            "total_stored": self._total_stored,
            "total_retrieved": self._total_retrieved,
            "base_dir": self._base_dir,
        }

    def clear(self) -> None:
        """Clear all entries (for testing)."""
        with self._lock:
            entry_ids = list(self._entries.keys())
            self._entries = {}
            self._total_stored = 0
            self._total_retrieved = 0

        # Clean up files outside the lock
        for output_id in entry_ids:
            # Find and remove the file directly (entry already removed from dict)
            file_path = os.path.join(self._base_dir, f"{output_id}.txt")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass


# ═══════════════════════════════════════════════════════════════════════
#  Global Instance
# ═══════════════════════════════════════════════════════════════════════

_global_store: Optional[ToolOutputStore] = None


def get_tool_output_store() -> ToolOutputStore:
    """Get the global ToolOutputStore instance."""
    global _global_store
    if _global_store is None:
        _global_store = ToolOutputStore()
    return _global_store