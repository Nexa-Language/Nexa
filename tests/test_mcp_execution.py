"""Official SDK protocol round trip over a real local stdio process."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mcp import StdioServerParameters, types
from mcp.server import Server

from src.runtime.mcp_client import MCPClient


def test_stdio_discovery_call_error_and_shutdown(tmp_path: Path) -> None:
    server = tmp_path / "server.py"
    server.write_text('''from mcp.server import MCPServer
server = MCPServer("fixture")
@server.tool()
def add(a: int, b: int) -> int:
    return a + b
@server.tool()
def fail() -> str:
    raise ValueError("fixture failure")
server.run()
''')
    client = MCPClient(target=StdioServerParameters(command=sys.executable, args=[str(server)]), timeout=5)
    with client:
        tools = client.get_tools_schema()
        assert {tool["name"] for tool in tools} == {"add", "fail"}
        assert all(tool["requires_approval"] for tool in tools)
        result = client.call_tool("add", a=2, b=3)
        assert result["structuredContent"]["result"] == 5
        with pytest.raises(RuntimeError, match="failed"):
            client.call_tool("fail")
    with pytest.raises(RuntimeError, match="not connected"):
        client.call_tool("add", a=1, b=2)


def test_mcp_missing_config_is_an_explicit_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        MCPClient(str(tmp_path / "missing.json"))


def test_official_sdk_discovers_all_pages() -> None:
    cursors = []

    async def list_tools(context: object, params: types.PaginatedRequestParams | None) -> types.ListToolsResult:
        cursor = params.cursor if params else None
        cursors.append(cursor)
        name = "second" if cursor else "first"
        return types.ListToolsResult(tools=[types.Tool(name=name, input_schema={"type": "object"})], next_cursor=None if cursor else "page2")

    server = Server("pagination", on_list_tools=list_tools)
    with MCPClient(target=server) as client:
        assert [tool["name"] for tool in client.get_tools_schema()] == ["first", "second"]
    assert cursors == [None, "page2"]


def test_disconnect_after_effect_has_unknown_outcome(tmp_path: Path) -> None:
    from src.runtime.tool_dispatch import ToolOutcomeUnknown

    marker = tmp_path / 'effect.txt'
    server = tmp_path / 'disconnect.py'
    server.write_text('''import os
from pathlib import Path
from mcp.server import MCPServer
server = MCPServer("disconnect")
@server.tool()
def disconnect() -> str:
    Path(''' + repr(str(marker)) + ''').write_text("effect happened")
    os._exit(0)
server.run()
''')
    with MCPClient(target=StdioServerParameters(command=sys.executable, args=[str(server)]), timeout=3) as client:
        with pytest.raises(ToolOutcomeUnknown):
            client.call_tool('disconnect')
    assert marker.read_text() == 'effect happened'
