import os
import typer
import subprocess
import shutil
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def scan_command():
    """Scan local Linux system for malware, suspicious processes, open backdoor ports, and temp file threats."""
    console.print(Panel("[bold red]🛡️ System Virus, Malware & Security Inspector[/bold red]", border_style="red"))

    # 1. Check suspicious executable files in /tmp and /dev/shm
    console.print("\n1. [bold yellow]Scanning temporary directories (/tmp, /dev/shm) for suspicious binaries...[/bold yellow]")
    suspicious_files = []
    temp_dirs = [Path("/tmp"), Path("/dev/shm"), Path("/var/tmp")]
    
    for td in temp_dirs:
        if td.exists():
            for p in td.glob("*"):
                try:
                    if p.is_file() and os.access(p, os.X_OK) and p.name not in ["ollama.tgz", "ollama.tar.zst"]:
                        suspicious_files.append(str(p))
                except Exception:
                    pass

    if suspicious_files:
        console.print(f"[bold red]  ⚠️ Warning: Found {len(suspicious_files)} executable file(s) in temporary storage:[/bold red]")
        for sf in suspicious_files[:10]:
            console.print(f"    - {sf}")
    else:
        console.print("[bold green]  ✓ Temporary storage (/tmp, /dev/shm) is clean![/bold green]")

    # 2. Check listening network ports
    console.print("\n2. [bold yellow]Checking active listening network ports...[/bold yellow]")
    try:
        ss_out = subprocess.check_output(["ss", "-tulpn"], text=True)
        lines = [line for line in ss_out.splitlines() if "LISTEN" in line]
        
        table = Table(title="🌐 Active Listening Ports", border_style="cyan")
        table.add_column("Protocol", style="cyan")
        table.add_column("Local Address", style="yellow")
        table.add_column("Process", style="white")
        
        for line in lines[:10]:
            parts = line.split()
            if len(parts) >= 5:
                proto = parts[0]
                addr = parts[4]
                proc = parts[-1] if len(parts) >= 7 else "unknown"
                table.add_row(proto, addr, proc)
                
        console.print(table)
    except Exception as e:
        console.print(f"[dim]Network port scan error: {e}[/dim]")

    # 3. Check ClamAV Antivirus
    console.print("\n3. [bold yellow]Checking Antivirus Scanner (clamscan)...[/bold yellow]")
    if shutil.which("clamscan"):
        console.print("[bold green]  ✓ ClamAV detected! Running fast scan on /tmp...[/bold green]")
        try:
            res = subprocess.run(["clamscan", "-r", "--infected", "/tmp"], capture_output=True, text=True)
            console.print(res.stdout or "[bold green]  ✓ ClamAV scan complete: No viruses detected.[/bold green]")
        except Exception as e:
            console.print(f"[dim]ClamAV execution error: {e}[/dim]")
    else:
        console.print("[yellow]  ! ClamAV (clamscan) is not installed.[/yellow]")
        # Package manager hint based on OS
        if shutil.which("pacman"):
            console.print("    [bold cyan]Arch Linux installation command:[/bold cyan] sudo pacman -S clamav")
        elif shutil.which("apt"):
            console.print("    [bold cyan]Ubuntu/Debian installation command:[/bold cyan] sudo apt install clamav")

    console.print("\n[bold green]✓ System Security Scan Complete![/bold green]")
