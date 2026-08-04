import typer
from rich.console import Console
from rich.table import Table
from rich import box
from capture_help.memory import add_memory, get_all_memories, clear_memories

app = typer.Typer(help="Manage background learned rules and user memory preferences.")
console = Console()

@app.command("list")
def list_memory():
    """List all background learned memories and rules."""
    memories = get_all_memories()
    if not memories:
        console.print("[yellow]No background learned memories found.[/yellow]")
        return

    table = Table(title="🧠 Learned Background Memories", box=box.ROUNDED, border_style="cyan")
    table.add_column("ID", style="bold yellow")
    table.add_column("Category", style="cyan")
    table.add_column("Learned Rule / Memory", style="bold white")
    table.add_column("Created At", style="dim")

    for m in memories:
        table.add_row(str(m["id"]), m["category"], m["content"], m["created_at"][:19])

    console.print(table)

@app.command("add")
def add_rule(
    rule: str = typer.Argument(..., help="Rule or memory preference to teach capture-help")
):
    """Teach capture-help a new background memory rule."""
    add_memory("user_preference", rule)
    console.print(f"[bold green]✓ Saved to background memory:[/bold green] [bold white]{rule}[/bold white]")

@app.command("clear")
def clear_all():
    """Clear all saved memories."""
    clear_memories()
    console.print("[bold green]✓ All background memories cleared.[/bold green]")
