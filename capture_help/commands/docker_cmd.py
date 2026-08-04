import typer
import subprocess
import shutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def docker_command():
    """Inspect Docker containers, images, and system resource usage."""
    console.print(Panel("[bold cyan]🐳 Docker & Container Intelligence[/bold cyan]", border_style="cyan"))

    if not shutil.which("docker"):
        console.print("[yellow]! Docker binary not found on your system.[/yellow]")
        console.print("[dim]Install Docker: [bold white]sudo pacman -S docker[/bold white] (Arch) or [bold white]sudo apt install docker.io[/bold white] (Debian/Ubuntu)[/dim]")
        return

    # 1. Containers list
    try:
        ps_out = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}"], text=True).strip()
        if ps_out:
            table = Table(title="📦 Active & Stopped Containers", border_style="cyan")
            table.add_column("Container ID", style="yellow")
            table.add_column("Name", style="bold white")
            table.add_column("Status", style="green")
            table.add_column("Image", style="dim")

            for line in ps_out.splitlines()[:10]:
                parts = line.split("\t")
                if len(parts) >= 4:
                    table.add_row(parts[0], parts[1], parts[2], parts[3])

            console.print(table)
        else:
            console.print("[green]✓ No active or stopped Docker containers found.[/green]")
    except Exception as e:
        console.print(f"[dim]Docker daemon error (is Docker service running?): {e}[/dim]")
