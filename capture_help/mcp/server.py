"""MCP server mode: expose capture-help capabilities as MCP tools.

Tools reuse existing capture-help modules (no duplicated logic). Command
execution keeps the interactive ``Confirm`` gate so no tool can silently run
shell commands. Built on the high-level ``MCPServer`` from the ``mcp`` SDK.
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()
log = Console(stderr=True)


def _confirm_command(command: str) -> bool:
    """Ask the operator to approve a command via the real terminal.

    In stdio MCP mode, stdout carries the JSON-RPC protocol and stdin carries
    incoming requests, so the prompt goes to stderr and the answer is read from
    /dev/tty. If no terminal is attached (headless client), execution is
    refused by default.
    """
    try:
        with open("/dev/tty", "r") as tty_in:
            log.print(f"[bold yellow]MCP run_command requested:[/bold yellow] [bold white]{command}[/bold white]")
            import sys
            sys.stderr.write("[bold yellow]Allow? [y/N]:[/bold yellow] ")
            sys.stderr.flush()
            answer = tty_in.readline().strip().lower()
            sys.stderr.write("\n")
            return answer in ("y", "yes")
    except Exception:
        log.print("[bold yellow]run_command refused: no interactive terminal available for confirmation.[/bold yellow]")
        return False


def _mcp_import_error() -> Optional[str]:
    try:
        import mcp  # noqa: F401
        return None
    except ImportError:
        return "The 'mcp' SDK is not installed. Install it with: pip install 'capture-help[mcp]'"


def build_server(name: str = "capture-help"):
    """Build and return the configured MCPServer instance with all tools registered."""
    from mcp.server.mcpserver import MCPServer

    server = MCPServer(
        name,
        title="capture-help",
        version="3.3.0",
        description="capture-help terminal AI assistant exposed over the Model Context Protocol",
    )
    @server.tool(name="search_codebase", description="Semantically search the local codebase for a query, returning ranked file snippets with scores.")
    def search_codebase(query: str, top_k: int = 4) -> str:
        from capture_help.project import search_project_context

        matches, scanned = search_project_context(query, top_k=top_k)
        if not matches:
            return f"No code matches found for '{query}' across {scanned} scanned files."
        out = [f"Found {len(matches)} match(es) across {scanned} scanned files:"]
        for file_path, text, score in matches:
            out.append(f"\nFile: {file_path} (Score: {score:.2f})\nSnippet:\n{text[:1500]}")
        return "\n".join(out)

    @server.tool(name="read_file", description="Read a source file from the project, optionally limiting the number of lines.")
    def read_file(path: str, max_lines: int = 200) -> str:
        from capture_help.project import find_project_root

        root = find_project_root()
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            return f"Error: File '{path}' does not exist."
        if resolved.is_dir():
            return f"Error: '{path}' is a directory."
        try:
            lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
            shown = lines[:max_lines]
            return f"--- {resolved} ({len(lines)} lines, showing {len(shown)}) ---\n" + "\n".join(shown)
        except Exception as e:
            return f"Error reading '{path}': {e}"

    @server.tool(name="get_git_diff", description="Return the current git diff (staged or unstaged, or a given ref).")
    def get_git_diff(ref: Optional[str] = None) -> str:
        from capture_help.utils import get_git_diff as _diff

        diff = _diff(ref)
        return diff or "No git diff found."

    @server.tool(name="fingerprint_project", description="Analyze the project root: detected languages, build systems, frameworks and git status.")
    def fingerprint_project() -> str:
        from capture_help.project import fingerprint_project as _fp

        data = _fp()
        return json.dumps(data, indent=2, default=str)

    @server.tool(name="scan_secrets", description="Scan the codebase for hardcoded API keys, tokens and credentials.")
    def scan_secrets() -> str:
        from capture_help.commands.secrets import SECRET_PATTERNS
        from capture_help.project import find_project_root, load_ignore_patterns
        import re

        root = find_project_root()
        ignore_patterns = load_ignore_patterns(root)
        valid_exts = {".py", ".js", ".ts", ".json", ".env", ".toml", ".yml", ".yaml", ".sh", ".c", ".cpp"}
        leaks = []
        for r, dirs, files in root.walk():
            dirs[:] = [d for d in dirs if d not in ignore_patterns and not any(i in d for i in ignore_patterns)]
            for f in files:
                p = r / f
                if p.suffix.lower() not in valid_exts and p.name != ".env":
                    continue
                try:
                    for idx, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        for pat, desc in SECRET_PATTERNS:
                            if re.search(pat, line):
                                leaks.append((str(p), idx, desc))
                except Exception:
                    pass
        if not leaks:
            return "Security audit passed: no hardcoded secrets detected."
        return "Potential secrets found:\n" + "\n".join(
            f"  {p}:{idx} ({desc})" for p, idx, desc in leaks[:50]
        )

    @server.tool(name="web_search", description="Live web search (DuckDuckGo) returning parsed result titles, URLs and snippets.")
    def web_search(query: str) -> str:
        from capture_help.commands.web import _fetch_search_results, _format_results

        results = _fetch_search_results(query)
        return _format_results(results)

    @server.tool(name="run_command", description="Execute a shell command. Requires interactive confirmation. Prefer other tools when possible.")
    def run_command(command: str) -> str:
        import subprocess

        if not _confirm_command(command):
            return "Command execution cancelled by user (no confirmation)."
        try:
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
            out = res.stdout.strip()
            if res.stderr.strip():
                out += f"\n[STDERR]:\n{res.stderr.strip()}"
            return out[:10_000] or "Command executed cleanly with 0 output."
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 60 seconds."
        except Exception as e:
            return f"Error executing command: {e}"

    @server.tool(name="summarize", description="Summarize git changes, a file, or a directory into key takeaways.")
    def summarize(target: Optional[str] = None, ref: Optional[str] = None) -> str:
        from pathlib import Path as _Path

        from capture_help.deepseek import get_provider as _get_provider

        content = ""
        description = "input"
        if target:
            path = _Path(target).expanduser().resolve()
            if not path.exists():
                return f"Error: Path not found: {target}"
            if path.is_dir():
                from capture_help.commands.summarize import _build_directory_context
                content = _build_directory_context(path)
                description = f"directory {path}"
            else:
                content = path.read_text(encoding="utf-8", errors="replace")[:40000]
                description = f"file {path}"
        else:
            from capture_help.utils import get_git_diff as _diff
            content = _diff(ref)[:40000]
            description = f"git diff {ref or 'staged/unstaged'}"

        if not content.strip():
            return "Nothing to summarize."
        provider = _get_provider()
        text, _ = provider.completion(
            [{"role": "user", "content": f"Summarize this {description} concisely into key takeaways.\n\n{content}"}],
            temperature=0.3,
        )
        return text

    return server


def serve_stdio() -> None:
    """Run the MCP server over stdio (the default transport for MCP clients).

    All human-readable output is written to stderr; stdout is reserved for the
    MCP JSON-RPC protocol.
    """
    err = _mcp_import_error()
    if err:
        log.print(f"[bold red]{err}[/bold red]")
        raise SystemExit(1)
    log.print("[bold green]⚡ capture-help MCP server running over stdio. Waiting for a client...[/bold green]")
    server = build_server()
    asyncio.run(server.run_stdio_async())


def serve_streamable_http(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the MCP server over Streamable HTTP for remote clients."""
    err = _mcp_import_error()
    if err:
        console.print(f"[bold red]{err}[/bold red]")
        raise SystemExit(1)
    console.print(f"[bold green]⚡ capture-help MCP server running on http://{host}:{port}/mcp[/bold green]")
    server = build_server()
    asyncio.run(server.run_streamable_http_async(host=host, port=port))