import typer
import httpx
from rich.console import Console
from rich.panel import Panel
from capture_help import __version__

console = Console()

def update_command():
    """Check for new capture-help releases on GitHub."""
    console.print(f"[bold cyan]🔍 Checking for capture-help updates... (Current: v{__version__})[/bold cyan]\n")
    try:
        res = httpx.get("https://api.github.com/repos/Sidharth7082/capture-help/releases/latest", timeout=5.0)
        if res.status_code == 200:
            latest = res.json().get("tag_name", "").lstrip("v")
            if latest and latest != __version__:
                console.print(Panel(
                    f"[bold green]🎉 A new release of capture-help is available: v{latest}[/bold green]\n"
                    f"[white]Current version: v{__version__}[/white]\n\n"
                    f"To upgrade, run:\n"
                    f"[bold yellow]pip install --upgrade git+https://github.com/Sidharth7082/capture-help.git[/bold yellow]",
                    title="⚡ Upgrade Available",
                    border_style="green"
                ))
            else:
                console.print(f"[bold green]✓ You are running the latest version of capture-help (v{__version__})![/bold green]")
        else:
            console.print(f"[yellow]Could not check GitHub releases (HTTP {res.status_code}).[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Offline or update check error: {e}[/yellow]")
