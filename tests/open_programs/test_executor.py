"""Exercise the actual OCI boundary against the pinned Python image."""

from __future__ import annotations

import json
import subprocess

import pytest

IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


@pytest.fixture
def executor():
    from src.open_programs.executor import OCIExecutor

    probe = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, check=False)
    if probe.returncode:
        pytest.skip("Pinned OCI test image is unavailable in the selected Docker context")
    return OCIExecutor()


def run(executor, body: str, **limits):
    from src.open_programs.model import Candidate, ExecutionSpec, Implementation

    candidate = Candidate(goal_digest="goal", implementation=Implementation(kind="python", body=body), capabilities=("sandbox.exec",))
    return executor.execute_candidate(candidate, ExecutionSpec(image=IMAGE, return_type="Json", input_json='{"value": 21}', **limits))


def test_container_executes_candidate_without_host_credentials(executor) -> None:
    report = run(executor, 'def solve(inputs):\n import os\n return {"answer": inputs["value"] * 2, "secret": os.getenv("OPENAI_API_KEY"), "uid": os.getuid()}')
    assert report.succeeded, report.error
    assert json.loads(report.output_json) == {"answer": 42, "secret": None, "uid": 65534}


def test_filesystem_and_network_are_isolated(executor) -> None:
    body = '''def solve(inputs):
 import os, socket
 blocked = []
 for path in ["/etc/escape", "/root/.ssh/id_rsa", "/var/run/docker.sock"]:
  try:
   with open(path, "w") as handle: handle.write("escape")
  except OSError: blocked.append(path)
 try:
  socket.create_connection(("1.1.1.1", 53), timeout=.2)
 except OSError: blocked.append("network")
 return blocked
'''
    report = run(executor, body)
    assert report.succeeded, report.error
    assert json.loads(report.output_json) == ["/etc/escape", "/root/.ssh/id_rsa", "/var/run/docker.sock", "network"]


def test_printed_success_does_not_override_process_failure(executor) -> None:
    report = run(executor, 'def solve(inputs):\n print("PASSED")\n raise RuntimeError("failed")')
    assert not report.succeeded
    assert report.exit_code != 0


def test_timeout_removes_container(executor) -> None:
    report = run(executor, 'def solve(inputs):\n while True: pass', timeout_seconds=1)
    assert not report.succeeded
    assert report.error == "execution_timeout"
    result = subprocess.run(["docker", "ps", "-aq", "--filter", f"name={report.container_name}"], capture_output=True, text=True, check=False)
    assert result.stdout.strip() == ""


def test_output_limit_stops_unbounded_candidate(executor) -> None:
    report = run(executor, 'def solve(inputs):\n while True: print("x" * 4096, flush=True)', max_output_bytes=8192)
    assert not report.succeeded
    assert report.error == "output_limit"


def test_executor_unavailable_has_no_host_fallback() -> None:
    from src.open_programs.executor import OCIExecutor
    from src.open_programs.model import Candidate, ExecutionSpec, Implementation, ProgramError

    executor = OCIExecutor(binary="/not-a-docker-binary")
    candidate = Candidate(goal_digest="goal", implementation=Implementation(kind="value", body="42"))
    with pytest.raises(ProgramError, match="executor_unavailable"):
        executor.execute_candidate(candidate, ExecutionSpec(image=IMAGE, return_type="Int"))


def test_memory_exhaustion_is_confined_and_container_is_removed(executor) -> None:
    report = run(executor, 'def solve(inputs):\n return len(bytearray(512 * 1024 * 1024))', memory_mb=64, timeout_seconds=10)
    assert not report.succeeded
    result = subprocess.run(["docker", "ps", "-aq", "--filter", f"name={report.container_name}"], capture_output=True, text=True, check=False)
    assert result.stdout.strip() == ""


def test_process_limit_blocks_additional_children(executor) -> None:
    body = '''def solve(inputs):
 import subprocess
 children = []
 blocked = False
 try:
  for _ in range(32):
   try: children.append(subprocess.Popen(["sleep", "10"]))
   except OSError:
    blocked = True
    break
 finally:
  for child in children: child.terminate()
  for child in children: child.wait()
 return {"blocked": blocked, "children": len(children)}
'''
    report = run(executor, body, pids=8, timeout_seconds=10)
    assert report.succeeded, report.error
    values = json.loads(report.output_json)
    assert values["blocked"] and values["children"] < 8


def test_patch_wrapper_is_a_type_failure_before_repository_checks(executor) -> None:
    from src.open_programs.model import Candidate, ExecutionSpec, Implementation

    candidate = Candidate(goal_digest="patch", capabilities=("sandbox.exec",),
                          implementation=Implementation(kind="python", body='def solve(inputs):\n return {"kind":"value","body":"{}"}'))
    report = executor.execute_candidate(candidate, ExecutionSpec(image=IMAGE, return_type="Patch"))
    assert not report.succeeded and report.error == "type_mismatch"
