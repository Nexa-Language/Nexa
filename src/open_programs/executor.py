"""Bounded, unprivileged OCI execution. Candidate code never runs in the host."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import threading
import time
import uuid

from .frontend import _literal_matches
from .model import Candidate, CommandReport, ExecutionReport, ExecutionSpec, PatchValue, ProgramError, RepositoryCase, WorkspaceSnapshot, canonical_json
from .workspace import patched_files

_RUNNER = '''import contextlib, json, sys
payload = json.load(sys.stdin)
with contextlib.redirect_stdout(sys.stderr):
    implementation = payload["implementation"]
    if implementation["kind"] == "value":
        result = json.loads(implementation["body"])
    else:
        scope = {"__name__": "__nexa_candidate__"}
        exec(compile(implementation["body"], "<candidate>", "exec"), scope)
        result = scope["solve"](payload["inputs"])
print("NEXA_RESULT:" + json.dumps(result, allow_nan=False, separators=(",", ":")))
'''

_REPOSITORY_RUNNER = '''import json, os, pathlib, sys, tempfile
payload = json.load(sys.stdin)
root = pathlib.Path("/tmp/repository")
root.mkdir()
for item in payload["files"]:
    if item["content"] is None:
        continue
    path = root / item["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(item["content"], encoding="utf-8")
    path.chmod(item["mode"] & 0o777)
os.chdir(root)
with tempfile.TemporaryFile() as stream:
    stream.write(payload["input"].encode("utf-8"))
    stream.seek(0)
    os.dup2(stream.fileno(), 0)
    os.execvpe(payload["argv"][0], payload["argv"], {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"})
'''


class OCIExecutor:
    def __init__(self, *, binary: str = "docker", context: str | None = None) -> None:
        self.command = [binary, *(["--context", context] if context else [])]

    def _command(self, arguments: list[str], *, timeout: float = 20) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run([*self.command, *arguments], capture_output=True, text=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ProgramError("executor_unavailable", "Docker could not complete the request", retryable=True) from error

    def _create(self, name: str, spec: ExecutionSpec, runner: str = _RUNNER) -> None:
        result = self._command([
            "create", "--name", name, "--pull=never", "--interactive", "--network=none", "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--user=65534:65534", f"--pids-limit={spec.pids}", f"--memory={spec.memory_mb}m",
            f"--memory-swap={spec.memory_mb}m", f"--cpus={spec.cpus}", "--tmpfs=/tmp:rw,noexec,nosuid,size=67108864", "--workdir=/tmp",
            "--entrypoint=python", spec.image, "-I", "-c", runner,
        ])
        if result.returncode:
            raise ProgramError("executor_unavailable", "Pinned image or required Docker isolation is unavailable", retryable=True)
        self._verify_isolation(name, spec)

    def _verify_isolation(self, name: str, spec: ExecutionSpec) -> None:
        result = self._command(["inspect", name])
        if result.returncode:
            raise ProgramError("isolation_unverified", "Cannot inspect the created container")
        item = json.loads(result.stdout)[0]
        host = item["HostConfig"]
        config = item["Config"]
        if (host["NetworkMode"] != "none" or not host["ReadonlyRootfs"] or "ALL" not in host["CapDrop"]
                or not any(option.startswith("no-new-privileges") for option in host["SecurityOpt"])
                or config["User"] != "65534:65534" or host["Memory"] != spec.memory_mb * 1024 * 1024
                or host["MemorySwap"] != spec.memory_mb * 1024 * 1024 or host["NanoCpus"] != int(spec.cpus * 1_000_000_000)
                or host["PidsLimit"] != spec.pids or host.get("Privileged") or host.get("Binds")
                or any(mount["Type"] != "tmpfs" for mount in item.get("Mounts", []))):
            raise ProgramError("isolation_unverified", "Docker did not apply the requested isolation")

    def execute_candidate(self, candidate: Candidate, spec: ExecutionSpec) -> ExecutionReport:
        if candidate.implementation.kind == "python" and "sandbox.exec" not in candidate.capabilities:
            raise ProgramError("capability_denied", "Python candidates require sandbox.exec")
        inputs = json.loads(spec.input_json)
        payload = canonical_json({"implementation": candidate.implementation.model_dump(), "inputs": inputs}).encode()
        if len(payload) > 1048576:
            raise ProgramError("input_limit", "Candidate and inputs exceed 1 MiB")
        output, code, error, name = self._run_isolated(payload, spec, _RUNNER)
        return self._report(output, code, error, name, spec)

    def execute_repository(self, base: WorkspaceSnapshot, patch: PatchValue, case: RepositoryCase, spec: ExecutionSpec) -> CommandReport:
        files = patched_files(base, patch)
        # Expected outputs stay in the controller and never enter the candidate container.
        payload = canonical_json({"files": [file.model_dump() for file in files], "argv": case.argv, "input": case.input_text}).encode()
        if len(payload) > 33554432:
            raise ProgramError("input_limit", "Repository check input exceeds 32 MiB")
        output, code, error, name = self._run_isolated(payload, spec, _REPOSITORY_RUNNER)
        return CommandReport(output=output.decode("utf-8", errors="replace"), exit_code=code, error=error, container_name=name)

    def _run_isolated(self, payload: bytes, spec: ExecutionSpec, runner: str) -> tuple[bytes, int, str, str]:
        name = f"nexa-op-{uuid.uuid4().hex}"
        created = False
        try:
            # Mark before create so a failed verification also removes this uniquely named container.
            created = True
            self._create(name, spec, runner)
            output, code, error = self._capture([*self.command, "start", "--attach", "--interactive", name], payload, spec)
            return output, code, error, name
        finally:
            if created:
                cleanup = self._command(["rm", "--force", name])
                if cleanup.returncode and "No such container" not in cleanup.stderr:
                    raise ProgramError("executor_cleanup_failed", f"Container {name} requires cleanup")

    def _capture(self, command: list[str], payload: bytes, spec: ExecutionSpec) -> tuple[bytes, int, str]:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert process.stdin is not None and process.stdout is not None
        stdin = process.stdin

        def send() -> None:
            try:
                stdin.write(payload)
                stdin.close()
            except (BrokenPipeError, OSError):
                return

        writer = threading.Thread(target=send, daemon=True)
        writer.start()
        output = bytearray()
        error = ""
        deadline = time.monotonic() + spec.timeout_seconds
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        error = "execution_timeout"
                        break
                    for key, _ in selector.select(timeout=min(0.1, max(deadline - time.monotonic(), 0))):
                        block = os.read(process.stdout.fileno(), 65536)
                        if not block:
                            selector.unregister(key.fileobj)
                            continue
                        output.extend(block[:max(spec.max_output_bytes - len(output), 0)])
                        if len(output) >= spec.max_output_bytes:
                            error = "output_limit"
                            break
                    if error:
                        break
            if error:
                process.kill()
            code = process.wait(timeout=10)
            return bytes(output), code, error
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stdout.close()
            writer.join(timeout=1)

    def _report(self, output: bytes, code: int, error: str, name: str, spec: ExecutionSpec) -> ExecutionReport:
        text = output.decode("utf-8", errors="replace")
        if error or code:
            return ExecutionReport(succeeded=False, error=error or "candidate_failed", exit_code=code, container_name=name, log=text[-4000:])
        lines = text.splitlines()
        if not lines or not lines[-1].startswith("NEXA_RESULT:"):
            return ExecutionReport(succeeded=False, error="missing_result", exit_code=code, container_name=name, log=text[-4000:])
        try:
            value = json.loads(lines[-1].removeprefix("NEXA_RESULT:"))
            encoded = canonical_json(value)
        except (ValueError, TypeError):
            return ExecutionReport(succeeded=False, error="invalid_result", exit_code=code, container_name=name)
        if not _literal_matches(value, spec.return_type):
            return ExecutionReport(succeeded=False, error="type_mismatch", exit_code=code, container_name=name)
        return ExecutionReport(succeeded=True, output_json=encoded, exit_code=code, container_name=name, log="\n".join(lines[:-1])[-4000:])
