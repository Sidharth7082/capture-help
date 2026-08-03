import sys
import re
import uuid
from typing import List, Dict, Optional
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.table import Table

from capture_help.config import settings, save_config
from capture_help.deepseek import get_provider
from capture_help.history import save_session
from capture_help.project import fingerprint_project
from capture_help.utils import print_header, render_project_badge, stream_response, get_git_diff
from capture_help.agent import (
    agent_read_file,
    agent_write_file,
    agent_run_command,
    agent_search_codebase,
)

console = Console()

AVAILABLE_MODELS = ["deepseek-chat", "deepseek-reasoner"]

def handle_slash_command(cmd_text: str, history: List[Dict[str, str]]) -> Tuple[bool, Optional[str]]:
    """Process slash commands typed in interactive chat. Returns (handled: bool, optional_system_msg)."""
    parts = cmd_text.strip().split(maxsplit=1)
    sub = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if sub == "/model":
        if not arg:
            table = Table(title="🤖 Active AI Model", border_style="cyan")
            table.add_column("Model Name", style="bold yellow")
            table.add_column("Status", style="bold green")
            for m in AVAILABLE_MODELS:
                status = "[bold green]✓ Active[/bold green]" if m == settings.deepseek_model else ""
                table.add_row(m, status)
            console.print(table)
            console.print("[dim]To switch models, type: [bold white]/model deepseek-reasoner[/bold white] or [bold white]/model deepseek-chat[/bold white][/dim]")
        else:
            save_config(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=arg,
            )
            console.print(f"[bold green]✓ Switched model to:[bold white] {arg}[/bold white]")
        return True, None

    if sub == "/read":
        if not arg:
            console.print("[bold red]Usage:[/bold red] /read <filepath>")
            return True, None
        content = agent_read_file(arg)
        console.print(f"[bold green]✓ File '{arg}' read into chat context.[/bold green]")
        history.append({"role": "user", "content": f"User shared file content for '{arg}':\n{content}"})
        return True, "File loaded into context."

    if sub == "/run":
        if not arg:
            console.print("[bold red]Usage:[/bold red] /run <command>")
            return True, None
        out = agent_run_command(arg)
        console.print(f"[bold cyan]Command Output:[/bold cyan]\n{out}")
        history.append({"role": "user", "content": f"Output of terminal command `{arg}`:\n{out}"})
        return True, "Command output added to context."

    if sub == "/search":
        if not arg:
            console.print("[bold red]Usage:[/bold red] /search <query>")
            return True, None
        results = agent_search_codebase(arg)
        console.print(f"[bold cyan]Codebase Search Results:[/bold cyan]\n{results}")
        history.append({"role": "user", "content": f"Codebase search results for '{arg}':\n{results}"})
        return True, "Search results added to context."

    if sub == "/diff":
        diff = get_git_diff()
        if not diff:
            console.print("[bold yellow]No git diff detected in project.[/bold yellow]")
        else:
            console.print(f"[bold cyan]Current Git Diff ({len(diff.splitlines())} lines)[/bold cyan]")
            history.append({"role": "user", "content": f"Current git diff:\n```diff\n{diff}\n```"})
        return True, "Git diff added to context."

    if sub in ["/help", "help"]:
        table = Table(title="⚡ In-Chat Slash Commands & Tools", border_style="cyan")
        table.add_column("Command", style="bold yellow")
        table.add_column("Description", style="white")
        table.add_row("/model [name]", "View or switch AI model (deepseek-chat, deepseek-reasoner)")
        table.add_row("/read <file>", "Read source file into AI chat context")
        table.add_row("/run <command>", "Run shell command and feed output to AI")
        table.add_row("/search <query>", "Search project codebase for keywords")
        table.add_row("/diff", "Attach current git diff to chat context")
        table.add_row("/clear", "Reset conversation history")
        table.add_row("/exit", "Save session and exit chat")
        console.print(table)
        return True, None

    return False, None

def chat_command(initial_messages: Optional[List[Dict[str, str]]] = None, session_id: Optional[str] = None):
    """Interactive AI Agent chat in the terminal with tools & slash commands."""
    print_header("Interactive Agentic Chat", "Type /help for commands. Type /exit to quit.")
    
    info = render_project_badge()
    system_prompt = (
        f"You are `capture-help`, an expert AI coding agent built for the terminal with full project awareness.\n"
        f"Project Context:\n"
        f"- Project Name: {info['name']}\n"
        f"- Languages: {', '.join(info['languages']) or 'Generic'}\n"
        f"- Build Systems: {', '.join(info['build_systems']) or 'N/A'}\n"
        f"You can answer coding questions, explain architecture, write code, and suggest fixes.\n"
        f"Available Slash Commands: /model, /read <file>, /run <cmd>, /search <query>, /diff, /clear, /exit."
    )

    history: List[Dict[str, str]] = initial_messages or []
    sess_id = session_id or str(uuid.uuid4())[:8]

    if history:
        console.print(f"[dim]Loaded {len(history)} previous message(s).[/dim]")

    while True:
        try:
            provider = get_provider()
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

            # Process In-Chat Slash Commands (/model, /read, /run, /search, /diff, /help)
            if user_input.startswith("/"):
                handled, sys_msg = handle_slash_command(user_input, history)
                if handled:
                    save_session(sess_id, history)
                    continue

            history.append({"role": "user", "content": user_input})
            
            console.print(f"[dim]Thinking ({settings.deepseek_model})...[/dim]")
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
