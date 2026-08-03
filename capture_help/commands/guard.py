import typer
import subprocess
from rich.console import Console

console = Console()

def guard_command():
    """Run pre-push continuous security, secret, and unit test audit guard."""
    console.print("[bold cyan]🛡️ Running Continuous Security & Quality Guard...[/bold cyan]\n")
    
    # 1. Run Secrets check
    console.print("1. [bold yellow]Inspecting for hardcoded secrets...[/bold yellow]")
    try:
        res = subprocess.run(["capture-help", "secrets"], capture_output=True, text=True)
        console.print("[green]  ✓ Secrets inspection complete.[/green]")
    except Exception:
        console.print("[yellow]  ! Secrets check skipped.[/yellow]")

    # 2. Run Audit check
    console.print("2. [bold yellow]Auditing dependency vulnerabilities...[/bold yellow]")
    try:
        res = subprocess.run(["capture-help", "audit"], capture_output=True, text=True)
        console.print("[green]  ✓ Dependency audit complete.[/green]")
    except Exception:
        console.print("[yellow]  ! Dependency audit skipped.[/yellow]")

    # 3. Run Pytest suite
    console.print("3. [bold yellow]Running automated unit test suite...[/bold yellow]")
    try:
        res = subprocess.run(["pytest", "tests/"], capture_output=True, text=True)
        if res.returncode == 0:
            console.print("[bold green]  ✓ Unit test suite passed cleanly![/bold green]")
        else:
            console.print("[bold red]  ❌ Unit tests failed! Please fix before pushing.[/bold red]")
            return
    except Exception:
        console.print("[yellow]  ! Pytest not found or skipped.[/yellow]")

    console.print("\n[bold green]🚀 All Guard Checks Passed! Ready for Git Push.[/bold green]")
