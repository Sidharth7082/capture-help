import sys
import uuid
from typing import List, Dict, Optional
from rich.console import Console
from rich.prompt import Prompt

from capture_help.deepseek import get_provider
from capture_help.history import save_session
from capture_help.project import fingerprint_project
from capture_help.utils import print_header, render_project_badge, stream_response

console = Console()

def chat_command(initial_messages: Optional[List[Dict[str, str]]] = None, session_id: Optional[str] = None):
    """Interactive AI chat in the terminal with project context & session persistence."""
    print_header("Interactive Chat", "Type /exit to quit. Type /clear to reset history.")
    
    info = render_project_badge()
    system_prompt = (
        f"You are `capture-help`, an expert AI coding assistant built for the terminal.\n"
        f"Working Directory / Project Info:\n"
        f"- Project Name: {info['name']}\n"
        f"- Languages: {', '.join(info['languages']) or 'Generic'}\n"
        f"- Build Systems: {', '.join(info['build_systems']) or 'N/A'}\n"
        f"Provide concise, accurate solutions with syntax highlighted code blocks."
    )

    provider = get_provider()
    history: List[Dict[str, str]] = initial_messages or []
    sess_id = session_id or str(uuid.uuid4())[:8]

    if history:
        console.print(f"[dim]Loaded {len(history)} previous message(s).[/dim]")

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]capture-help>[/bold cyan] ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["/exit", "exit", "quit", ":q"]:
                if history:
                    save_session(sess_id, history)
                    console.print(f"[dim]Session saved (ID: {sess_id}). Goodbye![/dim]")
                else:
                    console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() in ["/clear", "clear"]:
                history = []
                console.print("[green]✓ Chat history cleared.[/green]")
                continue

            if user_input.lower() in ["/help", "help"]:
                console.print("[yellow]Commands:[/yellow]\n  /clear - Clear chat history\n  /exit  - Quit chat session & save history\n  /help  - Show help message")
                continue

            history.append({"role": "user", "content": user_input})
            
            console.print("[dim]Thinking...[/dim]")
            gen = provider.stream_completion(messages=history, system_prompt=system_prompt)
            assistant_reply, stats = stream_response(gen, console)

            history.append({"role": "assistant", "content": assistant_reply})
            save_session(sess_id, history)

        except (KeyboardInterrupt, EOFError):
            if history:
                save_session(sess_id, history)
                console.print(f"\n[dim]Session saved (ID: {sess_id}). Session terminated.[/dim]")
            else:
                console.print("\n[dim]Session terminated.[/dim]")
            sys.exit(0)
