import typer
import subprocess
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def gpu_command():
    """Display GPU/VRAM hardware allocation and local inference health."""
    console.print("[bold cyan]📊 Local Hardware & VRAM Diagnostics[/bold cyan]")
    
    # 1. Check Ollama API Status
    ollama_status = "[red]Offline[/red]"
    try:
        res = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if res.status_code == 200:
            ollama_status = "[green]Active (http://localhost:11434)[/green]"
    except Exception:
        pass

    # 2. Check GPU VRAM via nvidia-smi or rocm-smi
    gpu_info = "CPU Only (No NVIDIA GPU detected)"
    try:
        smi = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"], text=True)
        lines = smi.strip().split("\n")
        if lines and lines[0]:
            name, total, used, free = [x.strip() for x in lines[0].split(",")]
            gpu_info = f"NVIDIA {name} | Used: {used}MB / {total}MB | Free: {free}MB"
    except Exception:
        pass

    table = Table(show_header=False, box=None)
    table.add_row("[bold yellow]Ollama Engine:[/bold yellow]", ollama_status)
    table.add_row("[bold yellow]GPU Acceleration:[/bold yellow]", gpu_info)
    table.add_row("[bold yellow]Default Model:[/bold yellow]", "[bold cyan]Google Gemma 3 12B (Q4)[/bold cyan]")
    table.add_row("[bold yellow]Inference Cost:[/bold yellow]", "[bold green]$0.00 USD (100% Free)[/bold green]")
    
    console.print(Panel(table, title="🖥️ Local AI Compute Stack", border_style="cyan"))
