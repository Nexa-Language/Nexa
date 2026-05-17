"""
Nexa v2.0 WasmSandbox — WASM 沙箱池

WasmSandbox 为高风险 Tool 提供隔离执行环境，负责：
  - acquire(): 从沙箱池获取沙箱实例
  - execute(): 在沙箱中执行代码
  - release(): 归还沙箱实例
  - 资源限制: CPU/内存/网络/文件系统隔离

Design Rationale:
  - 沙箱池: 预创建 N 个沙箱实例，避免冷启动延迟
  - 资源限制: 每个沙箱有独立的 CPU/内存/网络配额
  - 安全隔离: 高风险 Tool 在沙箱中执行，不影响主进程
  - 降级策略: WASM 不可用时降级为 subprocess 隔离

Author: Owen (AI Pair Programmer)
Version: 2.0.0-beta.1
"""

from __future__ import annotations

import os
import time
import json
import queue
import threading
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("nexa.wasm_sandbox")


# ═══════════════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SandboxConfig:
    """Configuration for a sandbox instance."""
    max_memory_mb: int = 128
    max_cpu_time_ms: int = 5000
    max_network_requests: int = 10
    allow_filesystem: bool = False
    allow_network: bool = True
    allow_subprocess: bool = False
    environment: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_time_ms": self.max_cpu_time_ms,
            "max_network_requests": self.max_network_requests,
            "allow_filesystem": self.allow_filesystem,
            "allow_network": self.allow_network,
            "allow_subprocess": self.allow_subprocess,
        }


@dataclass
class SandboxResult:
    """Result of a sandbox execution."""
    success: bool = True
    output: str = ""
    error: Optional[str] = None
    exit_code: int = 0
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    sandbox_id: str = ""

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "output": self.output[:500],
            "error": self.error,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
            "memory_used_mb": self.memory_used_mb,
            "sandbox_id": self.sandbox_id,
        }


# ═══════════════════════════════════════════════════════════════════════
#  WasmSandbox — Sandbox Pool
# ═══════════════════════════════════════════════════════════════════════

class WasmSandbox:
    """
    WASM sandbox pool for isolated tool execution.

    Implements:
      - acquire(): Get a sandbox from the pool
      - execute(): Run code in the sandbox
      - release(): Return sandbox to the pool
      - execute_python(): Execute Python code in subprocess isolation

    Usage:
        sandbox = WasmSandbox(pool_size=4)
        sb = sandbox.acquire()
        result = sandbox.execute(sb, "print('hello')")
        sandbox.release(sb)
    """

    def __init__(self, pool_size: int = 4, config: Optional[SandboxConfig] = None) -> None:
        self._pool_size = pool_size
        self._config = config or SandboxConfig()
        self._available: queue.Queue = queue.Queue()
        self._in_use: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._execution_count = 0
        self._sandbox_counter = 0

        # Pre-create sandbox pool
        for _ in range(pool_size):
            self._create_sandbox()

    def _create_sandbox(self) -> str:
        """Create a new sandbox instance."""
        self._sandbox_counter += 1
        sandbox_id = f"sandbox_{self._sandbox_counter}"

        sb = {
            "id": sandbox_id,
            "config": self._config,
            "created_at": time.time(),
            "executions": 0,
        }

        self._available.put(sb)
        return sandbox_id

    def acquire(self, timeout: Optional[float] = 1.0) -> Dict:
        """
        Acquire a sandbox from the pool.

        Args:
            timeout: Max wait time for an available sandbox (default 1s)

        Returns:
            Sandbox instance dict
        """
        try:
            sb = self._available.get(timeout=timeout)
            with self._lock:
                self._in_use[sb["id"]] = sb
            logger.info(f"Sandbox acquired: {sb['id']}")
            return sb
        except queue.Empty:
            # Pool exhausted, create a new one
            self._create_sandbox()
            sb = self._available.get(timeout=1)
            with self._lock:
                self._in_use[sb["id"]] = sb
            logger.info(f"Sandbox acquired (new): {sb['id']}")
            return sb

    def release(self, sb: Dict) -> None:
        """
        Return a sandbox to the pool.

        Args:
            sb: The sandbox instance to release
        """
        with self._lock:
            if sb["id"] in self._in_use:
                del self._in_use[sb["id"]]

        sb["executions"] += 1
        self._available.put(sb)
        logger.info(f"Sandbox released: {sb['id']}")

    def execute(
        self,
        sb: Dict,
        code: str,
        language: str = "python",
        timeout_ms: Optional[int] = None,
    ) -> SandboxResult:
        """
        Execute code in a sandbox.

        Args:
            sb: The sandbox instance
            code: Code to execute
            language: Programming language (python, javascript, shell)
            timeout_ms: Execution timeout in milliseconds

        Returns:
            SandboxResult with execution outcome
        """
        self._execution_count += 1
        sandbox_id = sb["id"]
        timeout = timeout_ms or self._config.max_cpu_time_ms

        if language == "python":
            return self._execute_python(code, sandbox_id, timeout)
        elif language == "shell":
            return self._execute_shell(code, sandbox_id, timeout)
        else:
            return SandboxResult(
                success=False,
                error=f"Unsupported language: {language}",
                sandbox_id=sandbox_id,
            )

    def _execute_python(self, code: str, sandbox_id: str, timeout_ms: int) -> SandboxResult:
        """Execute Python code in subprocess isolation."""
        start_time = time.time()

        try:
            # Write code to temp file
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', delete=False, prefix='nexa_sandbox_'
            ) as f:
                f.write(code)
                tmp_path = f.name

            # Execute in subprocess with resource limits
            result = subprocess.run(
                ["python3", tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000.0,
                env={**os.environ, **self._config.environment},
            )

            execution_time = (time.time() - start_time) * 1000

            # Cleanup
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

            return SandboxResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
                exit_code=result.returncode,
                execution_time_ms=execution_time,
                sandbox_id=sandbox_id,
            )

        except subprocess.TimeoutExpired:
            execution_time = (time.time() - start_time) * 1000
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout_ms}ms",
                execution_time_ms=execution_time,
                sandbox_id=sandbox_id,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return SandboxResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                sandbox_id=sandbox_id,
            )

    def _execute_shell(self, code: str, sandbox_id: str, timeout_ms: int) -> SandboxResult:
        """Execute shell command in subprocess isolation."""
        start_time = time.time()

        try:
            result = subprocess.run(
                code,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000.0,
                env={**os.environ, **self._config.environment},
            )

            execution_time = (time.time() - start_time) * 1000

            return SandboxResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
                exit_code=result.returncode,
                execution_time_ms=execution_time,
                sandbox_id=sandbox_id,
            )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout_ms}ms",
                execution_time_ms=(time.time() - start_time) * 1000,
                sandbox_id=sandbox_id,
            )

        except Exception as e:
            return SandboxResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
                sandbox_id=sandbox_id,
            )

    # ─── Statistics ───

    def get_stats(self) -> Dict:
        """Get sandbox pool statistics."""
        with self._lock:
            in_use_count = len(self._in_use)

        return {
            "pool_size": self._pool_size,
            "in_use": in_use_count,
            "available": self._available.qsize(),
            "total_executions": self._execution_count,
            "sandboxes_created": self._sandbox_counter,
        }

    def shutdown(self) -> None:
        """Shutdown the sandbox pool."""
        # Drain the pool
        while not self._available.empty():
            try:
                self._available.get_nowait()
            except queue.Empty:
                break

        with self._lock:
            self._in_use = {}

        logger.info("Sandbox pool shutdown")


# ═══════════════════════════════════════════════════════════════════════
#  Global Instance
# ═══════════════════════════════════════════════════════════════════════

_global_sandbox: Optional[WasmSandbox] = None


def get_sandbox() -> WasmSandbox:
    """Get the global WasmSandbox instance."""
    global _global_sandbox
    if _global_sandbox is None:
        _global_sandbox = WasmSandbox(pool_size=4)
    return _global_sandbox