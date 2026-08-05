"""`capture-help mcp` subcommand group: server, client, and registry management."""

import json
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from capture_help.mcp import config as mcp_config
from capture_help.mcp import client as mcp_client
from capture_help.mcp import server as mcp_server

app = typer.Typer(help="Model Context Protocol (MCP) server & client integration.")
console = Console()


@app.command("serve")
def serve(
    transport: str = typer.Option("stdio", "--transport", "-t", help="Transport: 'stdio' or 'http'."),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host for HTTP transport."),
    port: int = typer.Option(8765, "--port", "-p", help="Port for HTTP transport."),
):
    """Run the capture-help MCP server for external MCP clients."""
    if transport == "http":
        mcp_server.serve_streamable_http(host=host, port=port)
    else:
        mcp_server.serve_stdio()


@app.command("add")
def add(
    name: str = typer.Argument(..., help="Unique name for the MCP server (e.g. files, github)."),
    command: Optional[str] = typer.Option(None, "--command", "-c", help="Launch command for a stdio server (e.g. 'npx -y @modelcontextprotocol/server-filesystem /tmp')."),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="SSE/HTTP endpoint for a remote server."),
):
    """Register an external MCP server (stdio command or remote url)."""
    argv = command.split() if command else None
    err = mcp_config.validate_server({"name": name, "command": argv, "url": url})
    if err:
        console.print(f"[bold red]Error:[/bold red] {err}")
        raise typer.Exit(1)
    mcp_config.add_server(name, command=argv, url=url)
    console.print(f"[bold green]✓ Registered MCP server[/bold green] [bold white]{name}[/bold white]")
    console.print("Hint: [bold]capture-help mcp tools[/bold] to discover its tools, or use it in chat via [bold]TOOL_MCP: name.tool | {{...}}[/bold].")


@app.command("remove")
def remove(name: str = typer.Argument(..., help="Name of the registered MCP server to remove.")):
    """Remove a registered MCP server."""
    if mcp_config.remove_server(name):
        console.print(f"[bold green]✓ Removed MCP server[/bold green] [bold white]{name}[/bold white]")
    else:
        console.print(f"[bold yellow]No MCP server named '{name}' is registered.[/bold yellow]")


@app.command("list")
def list_servers():
    """List registered MCP servers and their enabled state."""
    servers = mcp_config.list_servers()
    if not servers:
        console.print("[yellow]No MCP servers registered. Add one with:[/yellow] [bold]capture-help mcp add <name> --command '...'[/bold]")
        return

    table = Table(title="Registered MCP Servers", box=box.ROUNDED, border_style="cyan")
    table.add_column("Name", style="bold yellow")
    table.add_column("Transport", style="cyan")
    table.add_column("Target", style="white")
    table.add_column("State", style="dim")

    for name, s in servers.items():
        if s.get("url"):
            transport, target = "HTTP", s["url"]
        else:
            transport, target = "stdio", " ".join(s.get("command") or [])
        state = "enabled" if s.get("enabled", True) else "disabled"
        table.add_row(name, transport, target, state)
    console.print(table)


@app.command("enable")
def enable(name: str = typer.Argument(..., help="Name of the MCP server to enable.")):
    """Enable a registered MCP server."""
    if mcp_config.set_enabled(name, True):
        console.print(f"[bold green]✓ Enabled MCP server[/bold green] [bold white]{name}[/bold white]")
    else:
        console.print(f"[bold yellow]No MCP server named '{name}' is registered.[/bold yellow]")


@app.command("disable")
def disable(name: str = typer.Argument(..., help="Name of the MCP server to disable.")):
    """Disable a registered MCP server (kept in config, not used by the agent)."""
    if mcp_config.set_enabled(name, False):
        console.print(f"[bold green]✓ Disabled MCP server[/bold green] [bold white]{name}[/bold white]")
    else:
        console.print(f"[bold yellow]No MCP server named '{name}' is registered.[/bold yellow]")


@app.command("ping")
def ping(name: str = typer.Argument(..., help="Name of the registered MCP server to test.")):
    """Test connectivity to a registered MCP server and list its tools."""
    ok, msg = mcp_client.ping(name)
    if ok:
        console.print(Panel(msg, border_style="green", expand=False))
        tools = mcp_client.list_tools(name)
        table = Table(title=f"Tools on '{name}'", box=box.ROUNDED, border_style="cyan")
        table.add_column("Tool", style="bold yellow")
        table.add_column("Description", style="white")
        for t in tools:
            table.add_row(t.get("name", "?"), (t.get("description") or "")[:80])
        console.print(table)
    else:
        console.print(f"[bold red]{msg}[/bold red]")


@app.command("tools")
def tools(
    name: Optional[str] = typer.Argument(None, help="Restrict to a single registered server."),
):
    """List tools discovered from registered MCP servers."""
    if name:
        entries = mcp_client.list_tools(name)
    else:
        entries = mcp_client.get_all_tools()

    errors = [e for e in entries if e.get("error")]
    if errors:
        for e in errors[:3]:
            console.print(f"[bold red]{e['error']}[/bold red]")
    tools_only = [e for e in entries if not e.get("error")]

    if not tools_only:
        console.print("[yellow]No tools discovered. Register servers with 'capture-help mcp add' or check connectivity with 'capture-help mcp ping <name>'.[/yellow]")
        return

    table = Table(title="Discovered MCP Tools", box=box.ROUNDED, border_style="cyan")
    table.add_column("Server", style="bold yellow")
    table.add_column("Tool", style="bold cyan")
    table.add_column("Description", style="white")
    for t in tools_only:
        table.add_row(t.get("server", "?"), t.get("name", "?"), (t.get("description") or "")[:90])
    console.print(table)


@app.command("call")
def call(
    name: str = typer.Argument(..., help="Registered MCP server name."),
    tool: str = typer.Argument(..., help="Tool name to invoke."),
    args: Optional[str] = typer.Option(None, "--args", "-a", help="JSON arguments, e.g. '{\"query\": \"config\"}'."),
):
    """Invoke a single MCP tool on a registered server (one-off test)."""
    try:
        arguments = json.loads(args) if args else {}
    except json.JSONDecodeError:
        console.print("[bold red]Error:[/bold red] --args must be valid JSON.")
        raise typer.Exit(1)

    console.print(f"[bold cyan]🔧 Calling {name}.{tool}[/bold cyan] {arguments}\n")
    result = mcp_client.call_tool(name, tool, arguments)
    console.print(result)


@app.command("scan")
def scan_config(
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Path to an existing mcp.json (e.g. ~/.config/opencode/opencode.json or ~/.claude.json)."),
):
    """Import MCP server definitions from another tool's config (Claude Desktop / opencode)."""
    from pathlib import Path

    target = Path(path).expanduser() if path else Path.home() / ".claude.json"
    if not target.exists():
        console.print(f"[bold yellow]No config found at {target}.[/bold yellow]")
        raise typer.Exit(1)

    imported = 0
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        candidates = {}
        if isinstance(raw, dict):
            if "mcpServers" in raw:
                candidates.update(raw["mcpServers"])
            if "mcp" in raw and isinstance(raw["mcp"], dict):
                for k, v in raw["mcp"].items():
                    if isinstance(v, dict) and "servers" in v:
                        candidates.update(v["servers"])
        for server_name, spec in candidates.items():
            if not isinstance(spec, dict):
                continue
            cmd = spec.get("command")
            args = spec.get("args") or []
            url = spec.get("url")
            if isinstance(cmd, str):
                mcp_config.add_server(server_name, command=[cmd, *[str(a) for a in args]], url=url)
                imported += 1
    except Exception as e:
        console.print(f"[bold red]Error importing config:[/bold red] {e}")
        raise typer.Exit(1)

    if imported:
        console.print(f"[bold green]✓ Imported {imported} MCP server(s) from {target}[/bold green]")
    else:
        console.print(f"[yellow]No MCP server definitions found in {target}.[/yellow]")
