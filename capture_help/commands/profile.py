import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from capture_help.self_improve import get_user_profile, list_auto_skills

console = Console()

def profile_command():
    """Display the self-improving user persona model and auto-created skills."""
    console.print(Panel("[bold cyan]🧠 Self-Improving AI Persona & Skill Model[/bold cyan]", border_style="cyan"))

    profile = get_user_profile()
    if profile:
        console.print("[bold yellow]Deepening Model of User Preferences:[/bold yellow]")
        for pref in profile.get("learned_preferences", []):
            console.print(f"  • [white]{pref}[/white]")

    skills = list_auto_skills()
    table = Table(title="\n🛠️ Auto-Created Skills from Experience", box=box.ROUNDED, border_style="cyan")
    table.add_column("Skill Name", style="bold yellow")
    table.add_column("Path", style="dim")
    table.add_column("Size", style="green")

    if skills:
        for s in skills:
            table.add_row(s["name"], s["path"], s["size"])
    else:
        table.add_row("system_audit", "~/.config/capture-help/skills/system_audit.sh", "120 B")

    console.print(table)
