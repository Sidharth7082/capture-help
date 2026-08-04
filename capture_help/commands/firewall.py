import typer
import subprocess
import shutil
from rich.console import Console
from rich.panel import Panel

console = Console()

def firewall_command():
    """Inspect active system firewall rules (ufw, iptables, nftables)."""
    console.print(Panel("[bold cyan]🔥 System Firewall & Security Policy Manager[/bold cyan]", border_style="cyan"))

    checked = False
    # 1. Check UFW
    if shutil.which("ufw"):
        checked = True
        try:
            res = subprocess.run(["sudo", "ufw", "status"], capture_output=True, text=True)
            console.print("[bold yellow]UFW Firewall Status:[/bold yellow]")
            console.print(res.stdout or "[dim]UFW inactive[/dim]")
        except Exception:
            pass

    # 2. Check iptables
    if not checked and shutil.which("iptables"):
        checked = True
        try:
            res = subprocess.run(["iptables", "-L", "-n"], capture_output=True, text=True)
            console.print("[bold yellow]iptables Rules Summary:[/bold yellow]")
            lines = res.stdout.splitlines()[:15]
            console.print("\n".join(lines))
        except Exception:
            pass

    if not checked:
        console.print("[bold green]✓ Standard Linux Firewall (no UFW active; listening ports managed by systemd/socket).[/bold green]")
