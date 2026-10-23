"""Official MCP SDK transport, tool discovery, and synchronous Agent bridge."""

from __future__ import annotations

import atexit
import json
import threading
import warnings
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from functools import partial
from pathlib import Path
from typing import Any


class MCPClient:
    def __init__(self, mcp_config_path: str | None = None, *, target: Any = None, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.target = target
        self._stack = ExitStack()
        self._client: Any = None
        self._portal: Any = None
        self._lock = threading.RLock()
        self._tools: dict[str, dict[str, Any]] = {}
        self._closed = False
        if mcp_config_path is not None:
            self.load_tools(mcp_config_path)

    def load_tools(self, filepath: str) -> None:
        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        if "tools" in data:
            warnings.warn("Static MCP tool catalogs provide schemas only; configure an MCP server to execute tools", DeprecationWarning, stacklevel=2)
            self._tools = {tool["name"]: {"name": tool["name"], "description": tool.get("description", ""),
                           "parameters": tool.get("parameters", {"type": "object", "properties": {}})} for tool in data["tools"]}
            return
        servers = data.get("mcpServers", {})
        if len(servers) != 1:
            raise ValueError("MCPClient configuration must contain exactly one mcpServers entry")
        config = next(iter(servers.values()))
        if "url" in config:
            self.target = config["url"]
        else:
            from mcp import StdioServerParameters
            self.target = StdioServerParameters(**config)

    def connect(self) -> MCPClient:
        with self._lock:
            if self._closed:
                raise RuntimeError("MCP client is closed")
            if self._client is not None:
                return self
            if self.target is None:
                raise ValueError("An MCP server target is required")
            try:
                from anyio.from_thread import start_blocking_portal
                from mcp import Client
            except ImportError as error:
                raise ImportError("Install nexa-lang[mcp] to use MCP servers") from error
            try:
                self._portal = self._stack.enter_context(start_blocking_portal())
                client = Client(self.target, read_timeout_seconds=self.timeout, cache=None)
                self._client = self._stack.enter_context(self._portal.wrap_async_context_manager(client))
                self._discover()
            except BaseException:
                self.close()
                raise
            return self

    def _discover(self) -> None:
        cursor = None
        seen: set[str] = set()
        for _ in range(100):
            page = self._portal.call(partial(self._client.list_tools, cursor=cursor))
            for tool in page.tools:
                if tool.name in self._tools:
                    raise ValueError(f"MCP returned duplicate tool name: {tool.name}")
                # Server annotations are hints, so they never grant approval or execution authority.
                self._tools[tool.name] = {"name": tool.name, "description": tool.description or "", "parameters": tool.input_schema,
                                          "_handler": partial(self.call_tool, tool.name), "requires_approval": True}
            cursor = page.next_cursor
            if cursor is None:
                return
            if cursor in seen:
                raise ValueError("MCP tool pagination repeated a cursor")
            seen.add(cursor)
        raise ValueError("MCP tool discovery exceeded 100 pages")

    def get_tools_schema(self) -> list[dict[str, Any]]:
        if self.target is not None and self._client is None:
            self.connect()
        return list(self._tools.values())

    def call_tool(self, name: str, **arguments: Any) -> dict[str, Any]:
        if self._closed or self._client is None:
            raise RuntimeError("MCP client is not connected")
        if name not in self._tools:
            raise ValueError(f"MCP tool was not discovered: {name}")
        from .tool_dispatch import ToolOutcomeUnknown
        try:
            result = self._portal.call(partial(self._client.call_tool, name, arguments, read_timeout_seconds=self.timeout))
        except Exception as error:
            raise ToolOutcomeUnknown(f"MCP tool {name} outcome is unknown") from error
        if result.is_error:
            raise RuntimeError(f"MCP tool {name} failed: {result.model_dump_json(exclude_none=True)}")
        return result.model_dump(exclude_none=True, by_alias=True)

    def close(self) -> None:
        with self._lock:
            self._stack.close()
            self._client = None
            self._closed = True

    def __enter__(self) -> MCPClient:  # noqa: PYI034 - Python 3.10 without an additional typing dependency.
        return self.connect()

    def __exit__(self, *args: object) -> None:
        self.close()


_clients: list[MCPClient] = []
_clients_lock = threading.Lock()
_scoped_clients: ContextVar[list[MCPClient] | None] = ContextVar("nexa_mcp_clients", default=None)


@contextmanager
def mcp_session_scope() -> Generator[None, None, None]:
    clients: list[MCPClient] = []
    token = _scoped_clients.set(clients)
    try:
        yield
    finally:
        _scoped_clients.reset(token)
        for client in reversed(clients):
            client.close()


def close_mcp_clients() -> None:
    with _clients_lock:
        clients = list(_clients)
        _clients.clear()
    for client in reversed(clients):
        client.close()


atexit.register(close_mcp_clients)


def fetch_mcp_tools(uri: str) -> list[dict[str, Any]]:
    client = MCPClient(target=uri) if uri.startswith(("https://", "http://")) else MCPClient(uri)
    try:
        schemas = client.get_tools_schema()
    except BaseException:
        client.close()
        raise
    scoped = _scoped_clients.get()
    if scoped is not None:
        scoped.append(client)
    else:
        with _clients_lock:
            _clients.append(client)
    return schemas
