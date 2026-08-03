import typer
import subprocess
import httpx
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage local Ollama models and local AI engine.")
console = Console()

@app.command("list")
def list_local_models():
    """List all installed local models in Ollama."""
    try:
        res = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        if res.status_code == 200:
            models = res.json().get("models", [])
            if not models:
                console.print("[yellow]No local models found in Ollama.[/yellow]")
                return
            
            table = Table(title="🥇 Installed Local Ollama Models")
            table.add_column("Model Name", style="cyan bold")
            table.add_column("Size", style="green")
            table.add_column("Modified", style="dim")
            
            for m in models:
                name = m.get("name", "unknown")
                size_gb = round(m.get("size", 0) / (1024**3), 2)
                modified = m.get("modified_at", "")[:10]
                table.add_row(name, f"{size_gb} GB", modified)
                
            console.print(table)
        else:
            console.print(f"[red]Error fetching models from Ollama: HTTP {res.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]Ollama server is not running at http://localhost:11434 ({e})[/red]")

@app.command("pull")
def pull_model(model_name: str = typer.Argument("gemma3:12b", help="Model name to pull (e.g., gemma3:12b, qwen2.5-coder)")):
    """Pull a model to local Ollama server."""
    console.print(f"[bold cyan]📥 Pulling model '{model_name}' to local Ollama...[/bold cyan]")
    try:
        subprocess.run(["ollama", "pull", model_name], check=True)
        console.print(f"[bold green]✓ Successfully pulled '{model_name}'![/bold green]")
    except Exception as e:
        console.print(f"[red]Failed to pull model '{model_name}': {e}[/red]")
