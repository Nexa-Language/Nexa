"""Provider adapters preserve messages, tool calls, usage, and opaque state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ModelRequest:
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    timeout: float
    stream: bool = False
    max_output_tokens: int | None = None
    response_format: dict[str, Any] | None = None
    tool_choice: str = "auto"
    provider_items: list[dict[str, Any]] = field(default_factory=list)
    provider_cursor: int = 0


@dataclass(frozen=True)
class ModelReply:
    message: dict[str, Any]
    input_tokens: int = 0
    output_tokens: int = 0
    usage_reported: bool = False
    provider_items: list[dict[str, Any]] = field(default_factory=list)
    provider_cursor: int = 0

    @property
    def text(self) -> str:
        return self.message.get("content") or ""

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        return self.message.get("tool_calls") or []


class ModelProvider(Protocol):
    name: str

    def complete(self, request: ModelRequest, on_text: Callable[[str], None] | None = None) -> ModelReply: ...


def object_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if hasattr(value, "dict"):
        return value.dict(exclude_none=True)
    raise TypeError(f"Provider returned unsupported message type: {type(value).__name__}")


class ChatCompletionsProvider:
    name = "chat"

    def __init__(self, client: Callable[[], Any], *, extra_body: dict[str, Any] | None = None,
                 max_tokens_field: Literal["max_tokens", "max_completion_tokens"] = "max_tokens") -> None:
        self._client = client
        self._extra_body = dict(extra_body or {})
        self._max_tokens_field = max_tokens_field

    def complete(self, request: ModelRequest, on_text: Callable[[str], None] | None = None) -> ModelReply:
        kwargs: dict[str, Any] = {"model": request.model, "messages": request.messages, "timeout": request.timeout}
        if self._extra_body:
            kwargs["extra_body"] = dict(self._extra_body)
        if request.max_output_tokens is not None:
            kwargs[self._max_tokens_field] = request.max_output_tokens
        if request.response_format is not None:
            kwargs["response_format"] = request.response_format
        if request.tools:
            kwargs["tools"] = [{"type": "function", "function": tool} for tool in request.tools]
            kwargs["tool_choice"] = request.tool_choice
        if request.stream:
            return self._stream(kwargs, on_text)
        response = self._client().chat.completions.create(**kwargs)
        if not response.choices:
            raise ValueError("Provider response contains no choices")
        if response.choices[0].finish_reason not in {"stop", "tool_calls"}:
            raise RuntimeError(f"Provider response was incomplete: {response.choices[0].finish_reason}")
        message = object_dict(response.choices[0].message)
        if message.get("refusal"):
            raise RuntimeError("Provider refused the request")
        usage = object_dict(response.usage) if response.usage is not None else {}
        return ModelReply(message, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), bool(usage))

    def _stream(self, kwargs: dict[str, Any], on_text: Callable[[str], None] | None) -> ModelReply:
        response = self._client().chat.completions.create(**kwargs, stream=True, stream_options={"include_usage": True})
        text: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        message: dict[str, Any] = {"role": "assistant"}
        usage: dict[str, Any] = {}
        finished = False
        finish_reason: str | None = None
        try:
            for chunk in response:
                if getattr(chunk, "usage", None) is not None:
                    usage = object_dict(chunk.usage)
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finished = finished or choice.finish_reason is not None
                finish_reason = choice.finish_reason or finish_reason
                delta = object_dict(choice.delta)
                if delta.get("content"):
                    text.append(delta["content"])
                    if on_text is not None:
                        on_text(delta["content"])
                for call in delta.pop("tool_calls", []):
                    target = calls.setdefault(call["index"], {"type": "function", "function": {"name": "", "arguments": ""}})
                    if call.get("id"):
                        target["id"] = call["id"]
                    for key in ("name", "arguments"):
                        target["function"][key] += call.get("function", {}).get(key, "")
                for key, value in delta.items():
                    if key not in {"content", "role"}:
                        message[key] = message.get(key, "") + value if isinstance(value, str) else value
        finally:
            if hasattr(response, "close"):
                response.close()
        if not finished:
            raise RuntimeError("Provider stream ended before a finish event")
        if finish_reason not in {"stop", "tool_calls"} or message.get("refusal"):
            raise RuntimeError("Provider stream was incomplete or refused")
        message["content"] = "".join(text)
        if calls:
            message["tool_calls"] = [calls[index] for index in sorted(calls)]
        return ModelReply(message, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), bool(usage))
