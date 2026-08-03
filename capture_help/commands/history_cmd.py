from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from capture_help.history import list_sessions, load_session
from capture_help.utils import print_header
from capture_help.commands.chat import chat_command

console = Console()

def history_command():
    """List recent saved chat sessions."""
    print_header("Session History Manager", "Saved terminal chat sessions")
    sessions = list_sessions()

    if not sessions:
        console.print("[dim]No saved chat sessions found.[/dim]\nRun 'capture-help chat' to start a new chat session!")
        return

    table = Table(title="📜 Recent Sessions", border_style="cyan", expand=True)
    table.add_column("#", style="bold yellow", width=4)
    table.add_column("Session Title", style="bold white")
    table.add_column("Date & Time", style="cyan")
    table.add_column("Turns", style="bold green")

    for i, sess in enumerate(sessions, 1):
        table.add_row(
            str(i),
            sess.get("title", "Chat Session"),
            sess.get("date_str", "Unknown"),
            str(sess.get("turns", 0)),
        )

    console.print(table)
    console.print("\n[dim]To resume a session, run:[bold white] capture-help resume <number_or_id>[/bold white][/dim]")

def resume_command(session_id: str):
    """Resume a previous chat session by ID or history index number."""
    sess_data = load_session(session_id)
    if not sess_data:
        console.print(f"[bold red]Error:[/bold red] Session '[yellow]{session_id}[/yellow]' not found.")
        return

    console.print(f"[bold green]✓ Resuming session:[/bold green] [bold white]{sess_data.get('title')}[/bold white]")
    chat_command(initial_messages=sess_data.get("messages", []), session_id=sess_data.get("id"))
