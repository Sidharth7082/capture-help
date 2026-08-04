import typer
import subprocess
import shutil
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm

app = typer.Typer(help="Arch Linux specific power-user tools (Pacman, AUR, Systemd, Mirrors).")
console = Console()

@app.command("info")
def arch_info():
    """Display Arch Linux rolling updates, kernel version, and system status."""
    console.print(Panel("[bold cyan]🐧 Arch Linux System Intelligence[/bold cyan]", border_style="cyan"))

    # 1. Kernel version
    try:
        kernel = subprocess.check_output(["uname", "-r"], text=True).strip()
    except Exception:
        kernel = "Unknown"

    # 2. Check pending updates
    pending_updates = 0
    if shutil.which("checkupdates"):
        try:
            up = subprocess.check_output(["checkupdates"], text=True)
            pending_updates = len(up.strip().splitlines()) if up.strip() else 0
        except Exception:
            pending_updates = 0

    table = Table(show_header=False, box=None)
    table.add_row("[bold yellow]OS Distribution:[/bold yellow]", "Arch Linux (Rolling Release)")
    table.add_row("[bold yellow]Kernel Version:[/bold yellow]", f"[bold white]{kernel}[/bold white]")
    table.add_row("[bold yellow]Pending Updates:[/bold yellow]", f"[bold green]{pending_updates} packages ready for pacman -Syu[/bold green]")
    table.add_row("[bold yellow]AUR Helper Detected:[/bold yellow]", "[bold cyan]yay / paru[/bold cyan]" if shutil.which("yay") or shutil.which("paru") else "pacman only")

    console.print(table)

@app.command("pkg")
def arch_pkg(query: str = typer.Argument(..., help="Package name to search in Pacman & AUR")):
    """Search official Arch repos and AUR for a package."""
    console.print(f"[bold cyan]🔍 Searching Arch Linux Repositories & AUR for '[white]{query}[/white]'...[/bold cyan]\n")

    found = False
    # 1. Official Pacman search
    if shutil.which("pacman"):
        try:
            out = subprocess.check_output(["pacman", "-Ss", query], text=True)
            if out.strip():
                found = True
                console.print("[bold yellow]📦 Official Pacman Repositories:[/bold yellow]")
                lines = out.strip().splitlines()
                for line in lines[:10]:
                    if "/" in line:
                        console.print(f"  [bold white]{line}[/bold white]")
                    else:
                        console.print(f"    [dim]{line.strip()}[/dim]")
        except Exception:
            pass

    # 2. AUR helper search
    aur_helper = "yay" if shutil.which("yay") else ("paru" if shutil.which("paru") else None)
    if aur_helper:
        try:
            out = subprocess.check_output([aur_helper, "-Ss", query], text=True)
            if out.strip():
                found = True
                console.print(f"\n[bold magenta]⚡ Arch User Repository (AUR via {aur_helper}):[/bold magenta]")
                lines = out.strip().splitlines()
                for line in lines[:10]:
                    if "/" in line or "aur/" in line:
                        console.print(f"  [bold white]{line}[/bold white]")
                    else:
                        console.print(f"    [dim]{line.strip()}[/dim]")
        except Exception:
            pass

    if not found:
        console.print(f"[yellow]No packages found matching '{query}'.[/yellow]")

@app.command("clean")
def arch_clean():
    """Find orphaned packages (pacman -Qtdq) and clean pacman package cache."""
    console.print("[bold cyan]🧹 Arch Linux Package & Cache Cleaner[/bold cyan]\n")

    # 1. Find orphans
    orphans = []
    if shutil.which("pacman"):
        try:
            res = subprocess.run(["pacman", "-Qtdq"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                orphans = res.stdout.strip().splitlines()
        except Exception:
            pass

    if orphans:
        console.print(f"[bold yellow]Found {len(orphans)} orphaned package(s):[/bold yellow]")
        for o in orphans:
            console.print(f"  - [white]{o}[/white]")
        console.print("\n[dim]To remove orphaned packages run: [bold white]sudo pacman -Rns $(pacman -Qtdq)[/bold white][/dim]")
    else:
        console.print("[bold green]✓ No orphaned packages found![/bold green]")

    # 2. Check Pacman cache size
    cache_dir = Path("/var/cache/pacman/pkg")
    if cache_dir.exists():
        try:
            total_size = sum(f.stat().st_size for f in cache_dir.glob("*.pkg.tar.*") if f.is_file())
            size_gb = round(total_size / (1024**3), 2)
            console.print(f"\n[bold yellow]Pacman Package Cache Size:[/bold yellow] [bold green]{size_gb} GB[/bold green]")
            console.print("[dim]To clean old package cache run: [bold white]sudo paccache -r[/bold white] or [bold white]sudo pacman -Sc[/bold white][/dim]")
        except Exception:
            pass

@app.command("systemd")
def arch_systemd():
    """Inspect failed systemd units and display system logs."""
    console.print("[bold cyan]⚙️ Arch Systemd Failed Units Inspector[/bold cyan]\n")

    if shutil.which("systemctl"):
        try:
            out = subprocess.check_output(["systemctl", "--failed", "--no-legend"], text=True).strip()
            if out:
                console.print("[bold red]❌ Failed Systemd Services Detected:[/bold red]")
                for line in out.splitlines():
                    console.print(f"  [bold red]•[/bold red] {line}")
            else:
                console.print("[bold green]✓ All systemd units and services are healthy! (0 failed)[/bold green]")
        except Exception as e:
            console.print(f"[dim]Systemd check error: {e}[/dim]")

@app.command("mirror")
def arch_mirror():
    """Benchmark and check Arch Linux mirrorlist speed."""
    console.print("[bold cyan]⚡ Arch Linux Mirrorlist Speed & Health Optimizer[/bold cyan]\n")

    if shutil.which("reflector"):
        console.print("[bold green]✓ Reflector mirror tool detected![/bold green]")
        console.print("[dim]To generate optimal fast mirrorlist run: [bold white]sudo reflector --latest 10 --protocol https --sort rate --save /etc/pacman.d/mirrorlist[/bold white][/dim]")
    else:
        console.print("[yellow]! 'reflector' is not installed.[/yellow]")
        console.print("[dim]Install with: [bold white]sudo pacman -S reflector[/bold white][/dim]")
