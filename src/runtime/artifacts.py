"""Content-addressed tool output with bounded, explicit reads."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from .tool_dispatch import ToolSpec


class ArtifactStore:
    def __init__(self, root: str | Path, max_read_chars: int = 8000) -> None:
        self.root = Path(root).resolve()
        self.max_read_chars = max_read_chars

    def put(self, content: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(content.encode()).hexdigest()
        descriptor, name = tempfile.mkstemp(dir=self.root, prefix=".pending-")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.root / key)
        finally:
            Path(name).unlink(missing_ok=True)
        return key

    def read(self, artifact_id: str, offset: int = 0, limit: int | None = None) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", artifact_id):
            raise ValueError("Invalid artifact ID")
        limit = min(4000, self.max_read_chars) if limit is None else limit
        if offset < 0 or not 1 <= limit <= self.max_read_chars:
            raise ValueError("Artifact read exceeds allowed range")
        path = self.root / artifact_id
        if path.is_symlink() or path.resolve().parent != self.root:
            raise ValueError("Artifact must be a regular file inside the run store")
        with path.open(encoding="utf-8") as handle:
            # Text offsets count Unicode characters, consistently with the output budget.
            remaining = offset
            while remaining:
                chunk = handle.read(min(remaining, 8192))
                if not chunk:
                    return ""
                remaining -= len(chunk)
            return handle.read(limit)

    def offload(self, content: str, budget: int) -> str:
        if len(content) <= budget:
            return content
        key = self.put(content)
        return json.dumps({"artifact_id": key, "characters": len(content), "preview": content[: min(512, budget // 4)],
                           "read_tool": "__nexa_read_artifact"}, ensure_ascii=False)

    def tool(self) -> ToolSpec:
        return ToolSpec("__nexa_read_artifact", "Read a bounded slice of a tool-output artifact. Offsets count characters.",
                        {"type": "object", "properties": {"artifact_id": {"type": "string"}, "offset": {"type": "integer", "minimum": 0},
                         "limit": {"type": "integer", "minimum": 1, "maximum": self.max_read_chars}}, "required": ["artifact_id"]}, self.read)
