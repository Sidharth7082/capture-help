"""MCP client: discover tools from registered external MCP servers and call them.

The ``mcp`` SDK is an optional extra. Every function imports it lazily so that
the rest of capture-help still works (and imports cleanly) when the extra is
missing. Errors surface as strings (never exceptions) so tool results can be
fed back into the agent loop.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Tuple

from rich.console import Console

from capture_help.mcp.config import enabled_servers, get_server

console = Console()

_MAX_RESULT_LEN = 10_000


def _mcp_import_error() -> Optional[str]:
    try:
        import mcp  # noqa: F401
        return None
    except ImportError:
        return (
            "The 'mcp' SDK is not installed. Install it with: "
            "pip install 'capture-help[mcp]'  (or: pip install mcp)"
        )


def _stringify_result(content) -> str:
    """Normalize a CallToolResult.content list (TextContent/ImageContent/...) into plain text."""
    if content is None:
        return ""
    parts = []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
            continue
        item_type = getattr(item, "type", None)
        if item_type in ("image", "resource"):
            parts.append(f"[{item_type} content]")
    return "\n".join(parts).strip()


def _fill_env(server: Dict) -> Dict[str, str]:
    """Merge current env with the server's configured env vars (if any)."""
    env = dict(os.environ)
    for k, v in (server.get("env") or {}).items():
        env[k] = v
    return env


def _connect(server: Dict):
    """Open an MCP session to a server (stdio command or SSE/HTTP url).

    Returns an async context manager yielding a connected ``ClientSession``.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client

    command = server.get("command")
    url = server.get("url")

    @asynccontextmanager
    async def _session():
        if url:
            async with sse_client(url, timeout=10) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        else:
            params = StdioServerParameters(command=command[0], args=command[1:], env=_fill_env(server))
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

    return _session


def list_tools(server_name: str) -> List[Dict]:
    """List normalized tools for a single registered server."""
    err = _mcp_import_error()
    if err:
        return [{"error": err}]

    server = get_server(server_name)
    if not server:
        return [{"error": f"No MCP server named '{server_name}' is registered."}]

    from mcp.client import Client

    try:
        if server.get("url"):
            async def _run():
                async with Client(server["url"]) as client:
                    result = await client.list_tools()
                    return _normalize_tools(result.tools)
            tools = asyncio.run(_run())
        else:
            async def _run2():
                async with _connect(server)() as session:
                    result = await session.list_tools()
                    return _normalize_tools(result.tools)
            tools = asyncio.run(_run2())
        return tools
    except Exception as e:
        return [{"error": f"Failed to list tools from '{server_name}': {e}"}]


def _normalize_tools(tools) -> List[Dict]:
    out = []
    for t in tools:
        schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)
        out.append({
            "name": getattr(t, "name", ""),
            "description": getattr(t, "description", "") or "",
            "input_schema": schema if isinstance(schema, dict) else {},
        })
    return out


def get_all_tools(limit: Optional[int] = None) -> List[Dict]:
    """Aggregate normalized tools across all enabled registered servers.

    Each entry carries ``server`` and ``name`` so the agent loop can address
    ``server.tool`` unambiguously. Silently skips unreachable servers.
    """
    err = _mcp_import_error()
    if err:
        return [{"error": err, "server": "", "name": ""}]

    all_tools: List[Dict] = []
    for server_name, server in enabled_servers().items():
        for tool in list_tools(server_name):
            if "error" in tool and tool.get("name") is None:
                all_tools.append({**tool, "server": server_name, "name": ""})
                continue
            all_tools.append({**tool, "server": server_name})
        if limit and len(all_tools) >= limit:
            break
    return all_tools


def available_tools_summary(limit: int = 15) -> str:
    """Compact 'Available MCP tools' block injected into the chat/agent system prompt."""
    err = _mcp_import_error()
    if err:
        return ""
    if not enabled_servers():
        return ""

    tools = [t for t in get_all_tools(limit=limit) if t.get("name") and not t.get("error")]
    if not tools:
        return ""

    lines = [
        "You can call external MCP tools via: TOOL_MCP: <server>.<tool> | <json args>",
        "Available MCP tools:",
    ]
    for t in tools:
        desc = (t.get("description") or "").strip().replace("\n", " ")[:80]
        lines.append(f"  - {t['server']}.{t['name']} :: {desc}")
    return "\n".join(lines)


def call_tool(server_name: str, tool_name: str, arguments: Optional[Dict] = None) -> str:
    """Invoke an MCP tool on a registered server and return the result as text."""
    err = _mcp_import_error()
    if err:
        return err

    server = get_server(server_name)
    if not server:
        return f"Error: No MCP server named '{server_name}' is registered."

    from mcp.client import Client

    try:
        if server.get("url"):
            async def _run():
                async with Client(server["url"]) as client:
                    result = await client.call_tool(tool_name, arguments or {})
                    return _stringify_result(result.content)
            text = asyncio.run(_run())
        else:
            async def _run2():
                async with _connect(server)() as session:
                    result = await session.call_tool(tool_name, arguments or {})
                    return _stringify_result(result.content)
            text = asyncio.run(_run2())
    except Exception as e:
        return f"Error calling tool '{server_name}.{tool_name}': {e}"

    if not text:
        text = f"[MCP {server_name}.{tool_name} returned an empty result]"
    return text[:_MAX_RESULT_LEN]


def ping(server_name: str) -> Tuple[bool, str]:
    """Connectivity check for a single server. Returns (ok, message)."""
    tools = list_tools(server_name)
    if tools and any("error" in t for t in tools):
        return False, tools[0]["error"]
    return True, f"MCP server '{server_name}' reachable ({len(tools)} tool(s))."