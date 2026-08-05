"""Tests for the MCP (Model Context Protocol) integration.

The mcp SDK is an optional extra; SDK-dependent tests skip gracefully when it
is missing. The shared conftest redirects MCP_CONFIG_FILE to tmp_path so the
user's real ~/.config/capture-help/mcp.json is never touched.
"""

import asyncio

import pytest

from typer.testing import CliRunner

from capture_help.cli import app
from capture_help.mcp import config as mcp_config
from capture_help.mcp import client as mcp_client
from capture_help.mcp import server as mcp_server

runner = CliRunner()

try:
    import mcp  # noqa: F401
    MCP_SDK_AVAILABLE = True
except ImportError:
    MCP_SDK_AVAILABLE = False

requires_mcp = pytest.mark.skipif(
    not MCP_SDK_AVAILABLE,
    reason="mcp SDK not installed (pip install 'capture-help[mcp]')",
)


# ---------------------------------------------------------------- config ---

def test_mcp_config_roundtrip():
    mcp_config.add_server("files", command=["npx", "server-filesystem", "/tmp"], url=None)
    assert "files" in mcp_config.list_servers()

    entry = mcp_config.get_server("files")
    assert entry["command"] == ["npx", "server-filesystem", "/tmp"]
    assert entry["enabled"] is True

    assert mcp_config.set_enabled("files", False) is True
    assert mcp_config.enabled_servers() == {}

    assert mcp_config.remove_server("files") is True
    assert mcp_config.remove_server("files") is False
    assert mcp_config.list_servers() == {}


def test_mcp_config_add_url():
    mcp_config.add_server("remote", command=None, url="http://localhost:8765/mcp")
    entry = mcp_config.get_server("remote")
    assert entry["url"] == "http://localhost:8765/mcp"
    mcp_config.remove_server("remote")


def test_mcp_config_validation():
    assert mcp_config.validate_server({"name": "x"}) is not None
    assert mcp_config.validate_server({"name": "x", "command": ["a"]}) is None
    assert mcp_config.validate_server({"name": "x", "url": "http://y"}) is None


# ---------------------------------------------------------------- server ---

@requires_mcp
def test_server_registers_expected_tools():
    server = mcp_server.build_server()

    async def _list():
        from mcp.client import Client
        async with Client(server) as c:
            result = await c.list_tools()
            return sorted(t.name for t in result.tools)

    tools = asyncio.run(_list())
    expected = {
        "search_codebase", "read_file", "get_git_diff", "fingerprint_project",
        "scan_secrets", "web_search", "run_command", "summarize",
    }
    assert expected.issubset(set(tools))


@requires_mcp
def test_server_search_codebase_tool(tmp_path, monkeypatch):
    (tmp_path / "greeter.py").write_text("def greet(name):\n    return f'hello {name}'\n")
    (tmp_path / "other.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)

    from capture_help.mcp.server import build_server

    server = build_server()

    async def _call():
        from mcp.client import Client
        async with Client(server) as c:
            res = await c.call_tool("search_codebase", {"query": "greet", "top_k": 2})
            return res.content[0].text

    text = asyncio.run(_call())
    assert "greeter.py" in text


@requires_mcp
def test_server_read_file_tool(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("line1\nline2\nline3\n")

    from capture_help.mcp.server import build_server

    server = build_server()

    async def _call():
        from mcp.client import Client
        async with Client(server) as c:
            res = await c.call_tool("read_file", {"path": str(f), "max_lines": 2})
            return res.content[0].text

    text = asyncio.run(_call())
    assert "line1" in text and "line2" in text and "line3" not in text


# ---------------------------------------------------------------- client ---

@requires_mcp
def test_get_all_tools_empty_registry(monkeypatch):
    # No servers registered -> no summary, no crash.
    assert mcp_client.available_tools_summary() == ""


def test_list_tools_unknown_server():
    assert "No MCP server named 'ghost' is registered." in mcp_client.list_tools("ghost")[0]["error"]


def test_call_tool_unknown_server():
    assert "No MCP server named 'ghost' is registered." in mcp_client.call_tool("ghost", "x")


def test_stringify_result(tmp_path, monkeypatch):
    class FakeText:
        type = "text"
        text = "hello"

    assert mcp_client._stringify_result([FakeText()]) == "hello"
    assert mcp_client._stringify_result([]) == ""


# ---------------------------------------------------------------- agent ---

def test_agent_tool_mcp_parsing(monkeypatch):
    """TOOL_MCP: server.tool | json args must route through mcp client call_tool."""
    from capture_help import agent

    calls = {}

    def fake_call(server_name, tool_name, arguments):
        calls["server"] = server_name
        calls["tool"] = tool_name
        calls["args"] = arguments
        return "mcp-ok"

    monkeypatch.setattr("capture_help.mcp.client.call_tool", fake_call)

    executed, log = agent.check_and_execute_agent_tools(
        'TOOL_MCP: files.read_file | {"path": "/tmp/x.txt"}'
    )
    assert executed is True
    assert calls == {"server": "files", "tool": "read_file", "args": {"path": "/tmp/x.txt"}}
    assert "[Tool Result MCP 'files.read_file']" in log
    assert "mcp-ok" in log


def test_agent_tool_mcp_bad_json(monkeypatch):
    from capture_help import agent

    monkeypatch.setattr("capture_help.mcp.client.call_tool", lambda s, t, a: "unused")

    executed, log = agent.check_and_execute_agent_tools(
        'TOOL_MCP: files.read_file | not-json'
    )
    assert executed is True
    assert "invalid json" in log.lower()


# ---------------------------------------------------------------- cli -----

def test_cli_mcp_help():
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0
    for cmd in ("serve", "add", "remove", "list", "tools", "call", "ping", "scan"):
        assert cmd in result.output


def test_cli_mcp_add_list_remove():
    result = runner.invoke(app, ["mcp", "add", "cli-test", "--command", "echo server"])
    assert result.exit_code == 0
    assert "cli-test" in mcp_config.list_servers()

    result = runner.invoke(app, ["mcp", "list"])
    assert result.exit_code == 0
    assert "cli-test" in result.output

    result = runner.invoke(app, ["mcp", "remove", "cli-test"])
    assert result.exit_code == 0
    assert "cli-test" not in mcp_config.list_servers()


def test_cli_mcp_add_validation():
    result = runner.invoke(app, ["mcp", "add", "broken"])
    assert result.exit_code != 0
    assert "must define" in result.output
