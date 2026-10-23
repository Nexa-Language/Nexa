"""Environment bindings resolve credentials only at an authorized model boundary."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


def test_chat_binding_preserves_explicit_provider_options() -> None:
    from src.runtime.providers import ChatCompletionsProvider, ModelRequest

    calls = []
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message={"content": "{}"})], usage={"prompt_tokens": 1, "completion_tokens": 1})
    def create(**kwargs):
        calls.append(kwargs)
        return response
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    provider = ChatCompletionsProvider(lambda: client, extra_body={"enable_thinking": False}, max_tokens_field="max_completion_tokens")
    provider.complete(ModelRequest(model="fixture", messages=[], tools=[], timeout=1, max_output_tokens=64))
    assert calls[0]["extra_body"] == {"enable_thinking": False}
    assert calls[0]["max_completion_tokens"] == 64
    assert "max_tokens" not in calls[0]


def test_environment_binds_endpoint_without_storing_credentials(tmp_path: Path, monkeypatch) -> None:
    from src.open_programs.environment import load_environment, model_provider
    from src.open_programs.model import ProgramError

    path = tmp_path / "environment.json"
    path.write_text(json.dumps({"image": IMAGE, "allow_model": True, "model": "fixture", "provider": {
        "api_key_env": "NEXA_TEST_KEY", "base_url_env": "NEXA_TEST_URL", "enable_thinking": False}}))
    monkeypatch.setenv("NEXA_TEST_URL", "https://example.com/v1")
    env = load_environment(path)
    with pytest.raises(ProgramError, match="credential_unavailable"), model_provider(env):
        pass
    monkeypatch.setenv("NEXA_TEST_KEY", "fixture-secret-do-not-serialize")
    assert "fixture-secret" not in env.model_dump_json()
    monkeypatch.setenv("NEXA_TEST_URL", "https://example.net/v1")
    assert load_environment(path).digest != env.digest
    with pytest.raises(ProgramError, match="endpoint_changed"), model_provider(env):
        pass


def test_cli_build_lock_and_author_stdio(tmp_path: Path) -> None:
    env = tmp_path / "env.json"
    env.write_text(json.dumps({"image": IMAGE}))
    source = tmp_path / "literal.nx"
    source.write_text('language "3.0" program Literal { goal answer() -> Int { intent "Return 42" implementation value 42 } }')
    command = [sys.executable, "-m", "src.cli", "build", str(source), "--environment", str(env), "--state", str(tmp_path / "state.db"), "--json"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    artifact = json.loads(result.stdout)
    assert artifact["results"][0]["output_json"] == "42"
    replay = subprocess.run([*command, "--locked"], capture_output=True, text=True, check=False)
    assert replay.returncode == 0, replay.stderr + replay.stdout
    assert json.loads(replay.stdout) == artifact
    assert not source.with_suffix(".py").exists()
    request = {"jsonrpc": "2.0", "id": 1, "method": "program/check", "params": {"source": source.read_text(), "path": str(source)}}
    author = subprocess.run([sys.executable, "-m", "src.cli", "author", "--state", str(tmp_path / "author.db")],
                            input=json.dumps(request) + "\n", capture_output=True, text=True, check=False)
    assert author.returncode == 0, author.stderr
    assert json.loads(author.stdout)["result"]["program"]["name"] == "Literal"
