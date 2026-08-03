from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from capture_help.plugins import BUILTIN_PLUGINS, get_enabled_plugins, save_enabled_plugins
from capture_help.utils import print_header

console = Console()

def plugin_command(action: str = "list", plugin_name: Optional[str] = None):
    """Manage domain-specific plugins and rule packages."""
    print_header("Domain Plugins & Custom Rules")

    enabled = get_enabled_plugins()

    if action.lower() in ["enable", "add"]:
        if not plugin_name:
            console.print("[bold red]Usage:[/bold red] capture-help plugin enable <plugin_name>")
            return
        p_key = plugin_name.lower().strip()
        if p_key not in BUILTIN_PLUGINS:
            console.print(f"[bold red]Error:[/bold red] Unknown plugin '{plugin_name}'. Run `capture-help plugin list` to see available plugins.")
            return

        if p_key not in enabled:
            enabled.append(p_key)
            save_enabled_plugins(enabled)

        console.print(Panel(
            f"[bold green]✓ Plugin '{BUILTIN_PLUGINS[p_key]['name']}' Enabled![/bold green]\n"
            f"[white]{BUILTIN_PLUGINS[p_key]['description']}[/white]",
            border_style="green",
            expand=False
        ))
        return

    if action.lower() in ["disable", "remove"]:
        if not plugin_name:
            console.print("[bold red]Usage:[/bold red] capture-help plugin disable <plugin_name>")
            return
        p_key = plugin_name.lower().strip()
        if p_key in enabled:
            enabled.remove(p_key)
            save_enabled_plugins(enabled)
            console.print(f"[bold yellow]✓ Plugin '{plugin_name}' disabled.[/bold yellow]")
        else:
            console.print(f"[dim]Plugin '{plugin_name}' is not currently enabled.[/dim]")
        return

    # List plugins
    table = Table(title="🔌 Domain Plugins & Custom Rules", border_style="cyan", expand=True)
    table.add_column("Plugin Key", style="bold yellow")
    table.add_column("Plugin Name", style="bold white")
    table.add_column("Status", style="bold green")
    table.add_column("Description", style="dim white")

    for key, data in BUILTIN_PLUGINS.items():
        status = "[bold green]✓ Enabled[/bold green]" if key in enabled else "[dim]Disabled[/dim]"
        table.add_row(key, data["name"], status, data["description"])

    console.print(table)
    console.print("\n[dim]To enable a plugin, run: [bold white]capture-help plugin enable <plugin_key>[/bold white][/dim]")
