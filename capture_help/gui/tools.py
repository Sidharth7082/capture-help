"""Text-only agent tool helpers for the Textual chat UI.

The legacy `capture_help.agent` module prints Rich panels and prompts for
confirmation, which cannot run inside a full-screen Textual app. These helpers
return plain strings so the UI can render them as tool cards and debug log
entries instead.
"""

import re
import subprocess
from pathlib import Path

from capture_help.agent import (
    agent_read_file,
    agent_search_codebase,
    agent_mcp_call,
    clean_tool_cmd,
)


def parse_tool_calls(text: str):
    """Extract embedded agent tool requests from an assistant reply.

    Returns a list of (kind, payload) tuples where kind is one of
    run / read / search / write / mcp.
    """
    calls = []
    for cmd in re.findall(r"TOOL_RUN:\s*([^\n]+)", text, re.IGNORECASE):
        calls.append(("run", clean_tool_cmd(cmd)))
    for path in re.findall(r"TOOL_READ:\s*([^\n]+)", text, re.IGNORECASE):
        calls.append(("read", clean_tool_cmd(path)))
    for q in re.findall(r"TOOL_SEARCH:\s*([^\n]+)", text, re.IGNORECASE):
        calls.append(("search", clean_tool_cmd(q)))
    blocks = [
        (m.start(), m.group(1).strip())
        for m in re.finditer(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    ]
    for m in re.finditer(r"TOOL_WRITE:\s*([^\n]+)", text, re.IGNORECASE):
        path = clean_tool_cmd(m.group(1))
        content = next((b for pos, b in blocks if pos > m.start()), "")
        calls.append(("write", (path, content)))
    for server, tool, args in re.findall(
        r"TOOL_MCP:\s*([\w.-]+)\.([\w.-]+)(?:\s*\|\s*(\{[^}]*\}|\S+))?", text, re.IGNORECASE
    ):
        calls.append(("mcp", (server, tool, args)))
    return calls


def run_command(command_str: str, timeout: int = 60) -> str:
    """Execute a shell command and return its combined output as text."""
    try:
        res = subprocess.run(
            command_str, shell=True, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout} seconds."
    except Exception as e:  # noqa: BLE001
        return f"Error executing command: {e}"

    out = ""
    if res.stdout.strip():
        out += res.stdout.strip()
    if res.stderr.strip():
        out += ("\n" if out else "") + "[stderr]\n" + res.stderr.strip()
    if not out:
        out = "Command executed cleanly with 0 output."
    return out[:10_000]


def write_file(filepath: str, content: str) -> str:
    """Write content to a file and return a status string."""
    try:
        path = Path(filepath).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Success: File '{path}' written successfully."
    except Exception as e:  # noqa: BLE001
        return f"Error writing file: {e}"


def execute_tool(kind: str, payload) -> str:
    """Dispatch a single parsed tool call to the right text helper."""
    if kind == "run":
        return run_command(payload)
    if kind == "read":
        return agent_read_file(payload)
    if kind == "search":
        return agent_search_codebase(payload)
    if kind == "write":
        return write_file(payload[0], payload[1]) if isinstance(payload, tuple) else write_file(payload, "")
    if kind == "mcp":
        server, tool, args = payload
        return agent_mcp_call(server, tool, args)
    return f"Error: unknown tool kind '{kind}'."
