"""Workspace-bound file operations for the Nexa Code example."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from .safe_eval import parse_safe_command


def workspace_path(path: str) -> Path:
    root = Path.cwd().resolve()
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Path must remain inside the current workspace")
    if any(part in {".git", ".ssh", ".aws"} for part in target.relative_to(root).parts) or target.name in {".env", "secrets.nxs"}:
        raise ValueError("Credential and repository-internal paths are not exposed to workspace tools")
    return target


def read_file(path: str) -> str:
    target = workspace_path(path)
    if target.stat().st_size > 2_000_000:
        raise ValueError("File exceeds the 2 MB text-read limit")
    return target.read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    target = workspace_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists():
            os.chmod(temporary, target.stat().st_mode & 0o777)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return f"Written {len(content)} characters to {path}"


def list_directory(path: str = ".") -> str:
    return "\n".join(item.name + ("/" if item.is_dir() else "") for item in sorted(workspace_path(path).iterdir())[:200])


def search_files(pattern: str, directory: str = ".") -> str:
    root = workspace_path(directory)
    matches: list[str] = []
    visited = 0
    for parent, directories, files in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if not name.startswith(".") and name not in {"node_modules", "target", "__pycache__"}]
        for name in files:
            visited += 1
            if visited > 2000:
                return "\n".join(matches) + "\n[Stopped after 2000 files]"
            path = Path(parent) / name
            if path.is_symlink() or name.startswith(".") or name == "secrets.nxs" or path.stat().st_size > 200_000:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for index, line in enumerate(lines, 1):
                if pattern in line:
                    matches.append(f"{path.relative_to(Path.cwd())}:{index}:{line}")
                    if len(matches) == 100:
                        return "\n".join(matches)
    return "\n".join(matches)


def shell_exec(command: str) -> str:
    """Run an approved command without a shell; this is not an OS sandbox."""
    if any(pattern in command.lower() for pattern in ("rm -rf", "drop database", "chmod 777", "dd", "mkfs")):
        raise ValueError("Command is blocked by the Nexa Code destructive-command policy")
    arguments = parse_safe_command(command)
    result = subprocess.run(arguments, shell=False, cwd=Path.cwd(), capture_output=True, text=True, timeout=30, check=False)
    if result.returncode:
        raise RuntimeError(f"Command exited {result.returncode}: {result.stderr[-4000:]}")
    return result.stdout
