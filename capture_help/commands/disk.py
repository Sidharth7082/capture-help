import typer
import subprocess
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def disk_command():
    """Inspect disk space partitions, mounted volumes, and large directories."""
    console.print(Panel("[bold cyan]💾 Disk Storage & Partition Analyzer[/bold cyan]", border_style="cyan"))

    # 1. Partition usage (df -h)
    try:
        df_out = subprocess.check_output(["df", "-h", "-x", "tmpfs", "-x", "devtmpfs"], text=True).strip()
        table = Table(title="📊 Mounted File Systems", border_style="cyan")
        lines = df_out.splitlines()
        if lines:
            headers = lines[0].split()
            for h in headers:
                table.add_column(h, style="bold white")
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 6:
                    table.add_row(*parts[:6])
        console.print(table)
    except Exception as e:
        console.print(f"[dim]df command error: {e}[/dim]")

    # 2. Reclaimable home directory files
    console.print("\n[bold yellow]📁 Home Directory Top Storage Consumers:[/bold yellow]")
    try:
        home = Path.home()
        dirs = []
        for item in home.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                try:
                    size = sum(f.stat().st_size for f in item.glob("**/*") if f.is_file())
                    dirs.append((item.name, size))
                except Exception:
                    pass

        dirs.sort(key=lambda x: x[1], reverse=True)
        for name, size in dirs[:5]:
            gb = round(size / (1024**3), 2)
            console.print(f"  • [bold white]{name}[/bold white]: [green]{gb} GB[/green]")
    except Exception:
        pass
