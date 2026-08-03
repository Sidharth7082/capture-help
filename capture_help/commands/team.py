from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, stream_response

console = Console()

TEAM_ROLES = [
    ("🏛️ Architect Agent", "Design system layout, interface contracts, and module boundaries."),
    ("💻 Coder Agent", "Implement core features, logic workflows, and helper functions."),
    ("🧪 Test Agent", "Write comprehensive unit tests, edge case assertions, and mocks."),
    ("🔒 Security Auditor", "Perform vulnerability assessment, input validation, and sanitization."),
]

def team_command(goal: str):
    """Launch multi-agent teamwork workflow with parallel specialized subagents."""
    print_header("Multi-Agent Teamwork Mode", goal)
    console.print(f"[bold cyan]🤖 Spawning Agent Team for Goal:[/bold cyan] [bold white]'{goal}'[/bold white]\n")

    provider = get_provider()

    for role_name, role_desc in TEAM_ROLES:
        console.print(Panel(f"[bold yellow]{role_name}[/bold yellow]\n[white]{role_desc}[/white]", border_style="cyan", expand=False))
        prompt = f"Role: {role_name}\nTask: {goal}\nGuidance: {role_desc}\nProvide your domain output for this goal."
        gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
        stream_response(gen, console)
        console.print()
