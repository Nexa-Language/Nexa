"""Native Responses and Anthropic adapters with lossless provider history."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

from .providers import ModelReply, ModelRequest, object_dict


class ResponsesProvider:
    name = "responses"

    def __init__(self, client: Callable[[], Any]) -> None:
        self._client = client

    def complete(self, request: ModelRequest, on_text: Callable[[str], None] | None = None) -> ModelReply:
        items = copy.deepcopy(request.provider_items)
        for message in request.messages[request.provider_cursor:]:
            if message["role"] == "tool":
                items.append({"type": "function_call_output", "call_id": message["tool_call_id"], "output": message["content"]})
            else:
                if message.get("content"):
                    items.append({"role": message["role"], "content": message["content"]})
                for call in message.get("tool_calls", []):
                    items.append({"type": "function_call", "call_id": call["id"], **call["function"]})
        kwargs: dict[str, Any] = {"model": request.model, "input": items, "timeout": request.timeout, "store": False,
                                  "include": ["reasoning.encrypted_content"]}
        if request.tools:
            kwargs["tools"] = [{"type": "function", **tool, "strict": False} for tool in request.tools]
            kwargs["tool_choice"] = request.tool_choice
        if request.max_output_tokens is not None:
            kwargs["max_output_tokens"] = request.max_output_tokens
        if request.response_format:
            form = request.response_format
            kwargs["text"] = {"format": {"type": "json_schema", **form["json_schema"]} if form["type"] == "json_schema" else form}
        response = self._stream(kwargs, on_text) if request.stream else self._client().responses.create(**kwargs)
        if response.status != "completed":
            raise RuntimeError(f"Responses request ended with status {response.status}")
        output = [object_dict(item) for item in response.output]
        if any(block.get("type") == "refusal" for item in output if item["type"] == "message" for block in item.get("content", [])):
            raise RuntimeError("Responses request was refused")
        calls = [{"id": item["call_id"], "type": "function", "function": {"name": item["name"], "arguments": item["arguments"]}}
                 for item in output if item["type"] == "function_call"]
        message: dict[str, Any] = {"role": "assistant", "content": response.output_text}
        if calls:
            message["tool_calls"] = calls
        usage = object_dict(response.usage) if response.usage is not None else {}
        return ModelReply(message, usage.get("input_tokens", 0), usage.get("output_tokens", 0), bool(usage),
                          items + output, len(request.messages) + 1)

    def _stream(self, kwargs: dict[str, Any], on_text: Callable[[str], None] | None) -> Any:
        stream = self._client().responses.create(**kwargs, stream=True)
        completed = None
        try:
            for event in stream:
                if event.type == "response.output_text.delta" and on_text is not None:
                    on_text(event.delta)
                elif event.type == "response.completed":
                    completed = event.response
                elif event.type in {"response.failed", "response.incomplete", "error"}:
                    raise RuntimeError(f"Responses stream failed: {event.type}")
        finally:
            stream.close()
        if completed is None:
            raise RuntimeError("Responses stream ended before completion")
        return completed


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client: Callable[[], Any]) -> None:
        self._client = client

    def complete(self, request: ModelRequest, on_text: Callable[[str], None] | None = None) -> ModelReply:
        messages = copy.deepcopy(request.provider_items)
        for message in request.messages[request.provider_cursor:]:
            role = message["role"]
            if role == "system":
                continue
            if role == "tool":
                block = {"type": "tool_result", "tool_use_id": message["tool_call_id"], "content": message["content"]}
                if messages and messages[-1]["role"] == "user" and isinstance(messages[-1]["content"], list):
                    messages[-1]["content"].append(block)
                else:
                    messages.append({"role": "user", "content": [block]})
            else:
                blocks: list[dict[str, Any]] = [{"type": "text", "text": message["content"]}] if message.get("content") else []
                for call in message.get("tool_calls", []):
                    blocks.append({"type": "tool_use", "id": call["id"], "name": call["function"]["name"],
                                   "input": json.loads(call["function"]["arguments"])})
                messages.append({"role": role, "content": blocks})
        kwargs: dict[str, Any] = {"model": request.model, "messages": messages, "timeout": request.timeout,
                                  "max_tokens": request.max_output_tokens or 4096}
        system = "\n".join(str(item.get("content", "")) for item in request.messages if item["role"] == "system")
        if system:
            kwargs["system"] = system
        if request.tools:
            kwargs["tools"] = [{"name": tool["name"], "description": tool.get("description", ""), "input_schema": tool["parameters"]}
                               for tool in request.tools]
            kwargs["tool_choice"] = {"type": "any" if request.tool_choice == "required" else request.tool_choice}
        if request.response_format:
            schema = request.response_format.get("json_schema", {}).get("schema", {"type": "object"})
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        if request.stream:
            with self._client().messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    if on_text is not None:
                        on_text(text)
                response = stream.get_final_message()
        else:
            response = self._client().messages.create(**kwargs)
        if response.stop_reason not in {"end_turn", "tool_use", "stop_sequence"}:
            raise RuntimeError(f"Anthropic request ended with stop reason {response.stop_reason}")
        blocks = [object_dict(block) for block in response.content]
        calls = [{"id": block["id"], "type": "function", "function": {"name": block["name"], "arguments": json.dumps(block["input"])}}
                 for block in blocks if block["type"] == "tool_use"]
        result: dict[str, Any] = {"role": "assistant", "content": "".join(block["text"] for block in blocks if block["type"] == "text")}
        if calls:
            result["tool_calls"] = calls
        usage = object_dict(response.usage)
        return ModelReply(result, usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0),
                          usage.get("output_tokens", 0), True, messages + [{"role": "assistant", "content": blocks}], len(request.messages) + 1)
