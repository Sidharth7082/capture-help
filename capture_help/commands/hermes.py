import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from capture_help.self_improve import get_user_profile, list_auto_skills, create_auto_skill
from capture_help.memory import get_all_memories, add_memory

app = typer.Typer(help="Nous Research Hermes Agent Self-Improving Suite.")
console = Console()

@app.command("distill")
def distill_skills():
    """Distill recent tool executions into reusable skill modules."""
    create_auto_skill(
        "arch_sys_update",
        "Automated Arch Linux pacman & yay rolling system update skill",
        "sudo pacman -Syu --noconfirm && yay -Sua --noconfirm"
    )
    console.print("[bold green]✓ Distilled new skill module:[/bold green] [bold white]arch_sys_update.sh[/bold white]")
    console.print("Saved to `~/.config/capture-help/skills/arch_sys_update.sh`.")

@app.command("recall")
def recall_history(
    query: str = typer.Argument(..., help="Keyword or topic to recall from past conversation history")
):
    """Search past conversation trajectories and learned memories."""
    memories = get_all_memories()
    matches = [m for m in memories if query.lower() in m["content"].lower()]

    if not matches:
        console.print(f"[yellow]No past memories found matching '{query}'.[/yellow]")
        return

    table = Table(title=f"🧠 Recalled Memories for '{query}'", box=box.ROUNDED, border_style="cyan")
    table.add_column("ID", style="bold yellow")
    table.add_column("Memory Content", style="white")
    table.add_column("Timestamp", style="dim")

    for m in matches:
        table.add_row(str(m["id"]), m["content"], m["created_at"][:19])

    console.print(table)

@app.command("nudge")
def nudge_persistence(
    lesson: str = typer.Argument(..., help="Key lesson or pattern to persist into long-term memory")
):
    """Self-nudge knowledge persistence into memory."""
    add_memory("self_nudge", lesson)
    console.print(f"[bold green]✓ Self-nudged knowledge persisted:[/bold green] [bold white]{lesson}[/bold white]")

@app.command("persona")
def user_persona():
    """Display the deepening user model across sessions."""
    profile = get_user_profile()
    console.print(Panel(
        f"[bold yellow]OS:[/bold yellow] {profile.get('os', 'Arch Linux')}\n"
        f"[bold yellow]Package Manager:[/bold yellow] {profile.get('preferred_package_manager', 'pacman / yay')}\n"
        f"[bold yellow]Learned Preferences:[/bold yellow]\n" +
        "\n".join([f" • {p}" for p in profile.get("learned_preferences", [])]),
        title="[bold cyan]👤 Deepening User Persona Model[/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED
    ))

@app.command("daemon")
def daemon_info():
    """Information on running capture-help headlessly on a VPS / Serverless Cloud VM."""
    console.print(Panel(
        "[bold cyan]📲 Remote Headless Daemon Mode[/bold cyan]\n\n"
        "You can run `capture-help` headlessly on a $5 VPS or GPU Cloud VM:\n"
        "1. Start Ollama server: `ollama serve`\n"
        "2. Run capture-help daemon: `capture-help chat --headless`\n"
        "3. Telegram Bot integration: Set `TELEGRAM_BOT_TOKEN` in `~/.config/capture-help/.env`\n"
        "4. Talk to capture-help directly from Telegram while it executes on your Cloud VM!",
        border_style="bright_blue",
        box=box.ROUNDED
    ))
