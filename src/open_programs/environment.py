"""Explicit model configuration; credentials never enter serialized environments."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from openai import OpenAI

from ..runtime.providers import ChatCompletionsProvider, ModelProvider
from .model import CompilerEnvironment, Dependency, ProgramError, ProviderBinding, content_digest


def _endpoint(binding: ProviderBinding) -> str:
    value = os.environ.get(binding.base_url_env, "")
    parts = urlsplit(value)
    if not value:
        raise ProgramError("endpoint_unavailable", binding.base_url_env)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ProgramError("endpoint_invalid", "Expected an HTTPS endpoint without embedded credentials")
    return value.rstrip("/")


def load_environment(path: Path) -> CompilerEnvironment:
    environment = CompilerEnvironment.model_validate_json(path.read_text(encoding="utf-8"))
    if environment.provider is None:
        return environment
    if any(dependency.name == "provider.endpoint" for dependency in environment.dependencies):
        raise ProgramError("reserved_dependency", "provider.endpoint is resolved by the controller")
    endpoint = Dependency(name="provider.endpoint", digest=content_digest(_endpoint(environment.provider)))
    return environment.model_copy(update={"dependencies": (*environment.dependencies, endpoint)})


@contextmanager
def model_provider(environment: CompilerEnvironment) -> Generator[ModelProvider | None, None, None]:
    if not environment.allow_model:
        yield None
        return
    binding = environment.provider
    if binding is None:
        raise ProgramError("model_unavailable", "Explicit provider binding is required")
    endpoint = _endpoint(binding)
    expected = next((item.digest for item in environment.dependencies if item.name == "provider.endpoint"), None)
    if expected != content_digest(endpoint):
        raise ProgramError("endpoint_changed", "Reload the compiler environment after changing its endpoint")
    key = os.environ.get(binding.api_key_env)
    if not key:
        raise ProgramError("credential_unavailable", binding.api_key_env)
    options = {} if binding.enable_thinking is None else {"enable_thinking": binding.enable_thinking}
    with OpenAI(api_key=key, base_url=endpoint, max_retries=0) as client:
        yield ChatCompletionsProvider(lambda: client, extra_body=options, max_tokens_field="max_completion_tokens")
