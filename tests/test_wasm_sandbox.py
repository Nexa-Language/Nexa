"""
Nexa v2.0 M6 Tests — WasmSandbox

Tests cover:
  - WasmSandbox: acquire/release, execute Python, execute shell
  - SandboxConfig, SandboxResult data structures
  - Pool exhaustion and recovery

Author: Owen (AI Pair Programmer)
Version: 2.0.0-beta.1
"""

import pytest
import time

from src.runtime.wasm_sandbox import (
    WasmSandbox, SandboxConfig, SandboxResult, get_sandbox,
)


class TestSandboxConfig:
    """SandboxConfig tests."""

    def test_default_config(self):
        config = SandboxConfig()
        assert config.max_memory_mb == 128
        assert config.max_cpu_time_ms == 5000

    def test_custom_config(self):
        config = SandboxConfig(max_memory_mb=256, allow_filesystem=True)
        assert config.max_memory_mb == 256
        assert config.allow_filesystem is True

    def test_to_dict(self):
        config = SandboxConfig(max_memory_mb=64)
        d = config.to_dict()
        assert d["max_memory_mb"] == 64


class TestSandboxResult:
    """SandboxResult tests."""

    def test_success_result(self):
        result = SandboxResult(success=True, output="hello", sandbox_id="sb_1")
        assert result.success is True
        assert result.output == "hello"

    def test_error_result(self):
        result = SandboxResult(success=False, error="timeout", sandbox_id="sb_1")
        assert result.success is False
        assert result.error == "timeout"

    def test_to_dict(self):
        result = SandboxResult(success=True, output="ok", sandbox_id="sb_1")
        d = result.to_dict()
        assert d["success"] is True
        assert d["sandbox_id"] == "sb_1"


class TestWasmSandbox:
    """WasmSandbox pool and execution tests."""

    def test_acquire_release(self):
        """Acquire and release a sandbox."""
        sandbox = WasmSandbox(pool_size=2)
        sb = sandbox.acquire()
        assert sb["id"].startswith("sandbox_")
        sandbox.release(sb)

    def test_execute_python(self):
        """Execute Python code in sandbox."""
        sandbox = WasmSandbox(pool_size=2)
        sb = sandbox.acquire()
        result = sandbox.execute(sb, "print('hello from sandbox')", language="python")
        sandbox.release(sb)

        assert result.success is True
        assert "hello from sandbox" in result.output

    def test_execute_python_error(self):
        """Python execution error is captured."""
        sandbox = WasmSandbox(pool_size=2)
        sb = sandbox.acquire()
        result = sandbox.execute(sb, "raise ValueError('test error')", language="python")
        sandbox.release(sb)

        assert result.success is False

    def test_execute_python_timeout(self):
        """Python execution timeout is enforced."""
        sandbox = WasmSandbox(pool_size=2)
        sb = sandbox.acquire()
        result = sandbox.execute(
            sb,
            "import time; time.sleep(10)",
            language="python",
            timeout_ms=500,
        )
        sandbox.release(sb)

        assert result.success is False
        assert "timed out" in (result.error or "")

    def test_execute_shell(self):
        """Execute shell command in sandbox."""
        sandbox = WasmSandbox(pool_size=2)
        sb = sandbox.acquire()
        result = sandbox.execute(sb, "echo 'hello shell'", language="shell")
        sandbox.release(sb)

        assert result.success is True
        assert "hello shell" in result.output

    def test_execute_unsupported_language(self):
        """Unsupported language returns error."""
        sandbox = WasmSandbox(pool_size=2)
        sb = sandbox.acquire()
        result = sandbox.execute(sb, "code", language="rust")
        sandbox.release(sb)

        assert result.success is False
        assert "Unsupported" in result.error

    def test_pool_exhaustion_creates_new(self):
        """Pool exhaustion creates new sandbox."""
        sandbox = WasmSandbox(pool_size=1)
        sb1 = sandbox.acquire()
        sb2 = sandbox.acquire()  # Should create new
        assert sb1["id"] != sb2["id"]
        sandbox.release(sb1)
        sandbox.release(sb2)

    def test_stats(self):
        """Sandbox stats are accurate."""
        sandbox = WasmSandbox(pool_size=2)
        sb = sandbox.acquire()
        sandbox.execute(sb, "print('test')", language="python")
        sandbox.release(sb)

        stats = sandbox.get_stats()
        assert stats["total_executions"] == 1
        assert stats["pool_size"] == 2

    def test_shutdown(self):
        """Shutdown drains the pool."""
        sandbox = WasmSandbox(pool_size=2)
        sandbox.shutdown()
        stats = sandbox.get_stats()
        assert stats["available"] == 0
        assert stats["in_use"] == 0