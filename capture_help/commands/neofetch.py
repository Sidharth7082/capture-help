import typer
import subprocess
import shutil
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich import box
from capture_help import __version__

console = Console()

ARCH_ASCII = """[bold cyan]
      /\\
     /  \\
    /\\   \\
   /      \\
  /   ,,   \\
 /   |  |  -\\
/_-''    ''-_\\
[/bold cyan]"""

def neofetch_command():
    """Display a stunning graphical system & AI dashboard card with Arch Linux ASCII art."""
    # 1. System info gathering
    try:
        kernel = subprocess.check_output(["uname", "-r"], text=True).strip()
    except Exception:
        kernel = "Linux"

    try:
        cpu = subprocess.check_output(["lscpu"], text=True)
        cpu_name = [l.split(":")[1].strip() for l in cpu.splitlines() if "Model name" in l][0]
    except Exception:
        cpu_name = "x86_64 CPU"

    try:
        mem = subprocess.check_output(["free", "-h"], text=True).splitlines()[1].split()
        mem_str = f"{mem[2]} / {mem[1]}"
    except Exception:
        mem_str = "N/A"

    # Specs Table
    specs_table = Table(show_header=False, box=box.ROUNDED, border_style="cyan")
    specs_table.add_column("Key", style="bold yellow")
    specs_table.add_column("Value", style="bold white")

    specs_table.add_row("OS Distribution", "Arch Linux (Rolling Release)")
    specs_table.add_row("Kernel Version", kernel)
    specs_table.add_row("Processor (CPU)", cpu_name[:35])
    specs_table.add_row("Memory (RAM)", mem_str)
    specs_table.add_row("AI Assistant", f"capture-help v{__version__}")
    specs_table.add_row("Local AI Model", "Google Gemma 3 12B (Q4)")
    specs_table.add_row("Local Engine", "Ollama (http://localhost:11434)")
    specs_table.add_row("Inference Cost", "$0.00 USD (100% Free)")

    dash_panel = Panel(
        Columns([ARCH_ASCII, specs_table], expand=True),
        title="[bold cyan]⚡ Arch Linux & AI Compute Dashboard[/bold cyan]",
        border_style="bright_blue",
        box=box.ROUNDED,
    )
    console.print(dash_panel)
