import sys
import uuid
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from capture_help.config import settings, save_config
from capture_help.deepseek import get_provider, DEEPSEEK_MODELS
from capture_help.history import save_session
from capture_help.project import fingerprint_project
from capture_help.utils import print_header, render_project_badge, stream_response, get_git_diff
from capture_help.agent import (
    agent_read_file,
    agent_write_file,
    agent_run_command,
    agent_search_codebase,
    check_and_execute_agent_tools,
)

console = Console()

COMPACT_SYSTEM_PROMPT = """You are capture-help, an AI terminal assistant powered by DeepSeek.
Be concise, direct, and output token-efficient solutions with clean code blocks.
Commands: /model, /read <file>, /run <cmd>, /search <query>, /diff, /clear, /exit."""

def handle_slash_command(cmd_text: str, history: List[Dict[str, str]]) -> Tuple[bool, Optional[str]]:
    parts = cmd_text.strip().split(maxsplit=1)
    sub = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if sub == "/model":
        if not arg:
            table = Table(title="🤖 Official DeepSeek Models", border_style="cyan")
            table.add_column("Model Key", style="bold yellow")
            table.add_column("Model Name", style="bold white")
            table.add_column("Status", style="bold green")
            table.add_column("Input Cost (per 1M)", style="green")
            for key, data in DEEPSEEK_MODELS.items():
                status = "[bold green]✓ Active[/bold green]" if key == settings.deepseek_model else ""
                table.add_row(key, data["name"], status, f"${data['input_cost_per_m']:.2f}")
            console.print(table)
            console.print("[dim]To switch model: [bold white]/model deepseek-v4-flash[/bold white] or [bold white]/model deepseek-chat[/bold white][/dim]")
        else:
            p_key = arg.lower().strip()
            if p_key in DEEPSEEK_MODELS:
                save_config(
                    api_key=settings.deepseek_api_key,
                    base_url=settings.deepseek_base_url,
                    model=p_key,
                )
                console.print(f"[bold green]✓ Switched active model to:[bold white] {DEEPSEEK_MODELS[p_key]['name']} ({p_key})[/bold white]")
            else:
                console.print(f"[bold red]Unknown model '{arg}'.[/bold red] Run `/model` to see available models.")
        return True, None

    if sub == "/cheap":
        save_config(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model="deepseek-v4-flash",
        )
        console.print("[bold green]⚡ Ultra-Cheap Mode Activated![/bold green] Active model: [bold white]deepseek-v4-flash[/bold white] ($0.07 / 1M tokens)")
        return True, None

    if sub in ["/plan", "/goal"]:
        prompt_goal = arg or "Plan step-by-step implementation"
        console.print(f"[bold cyan]🎯 Goal:[/bold cyan] [bold white]{prompt_goal}[/bold white]")
        history.append({
            "role": "user",
            "content": f"Create a concise step-by-step plan for: {prompt_goal}."
        })
        return False, "Goal added to context."

    if sub == "/read":
        if not arg:
            console.print("[bold red]Usage:[/bold red] /read <filepath>")
            return True, None
        content = agent_read_file(arg)
        console.print(f"[bold green]✓ File '{arg}' loaded into context.[/bold green]")
        history.append({"role": "user", "content": f"File content '{arg}':\n{content[:4000]}"})
        return True, "File loaded into context."

    if sub == "/run":
        if not arg:
            console.print("[bold red]Usage:[/bold red] /run <command>")
            return True, None
        out = agent_run_command(arg)
        console.print(f"[bold cyan]Command Output:[/bold cyan]\n{out}")
        history.append({"role": "user", "content": f"Terminal output of `{arg}`:\n{out[:3000]}"})
        return True, "Command output added."

    if sub == "/search":
        if not arg:
            console.print("[bold red]Usage:[/bold red] /search <query>")
            return True, None
        results = agent_search_codebase(arg)
        console.print(f"[bold cyan]Search Results:[/bold cyan]\n{results}")
        history.append({"role": "user", "content": f"Search results for '{arg}':\n{results[:3000]}"})
        return True, "Search results added."

    if sub == "/diff":
        diff = get_git_diff()
        if not diff:
            console.print("[bold yellow]No git diff detected.[/bold yellow]")
        else:
            console.print(f"[bold cyan]Git Diff ({len(diff.splitlines())} lines)[/bold cyan]")
            history.append({"role": "user", "content": f"Git diff:\n```diff\n{diff[:4000]}\n```"})
        return True, "Diff added."

    if sub in ["/help", "help"]:
        table = Table(title="⚡ Slash Commands", border_style="cyan")
        table.add_column("Command", style="bold yellow")
        table.add_column("Description", style="white")
        table.add_row("/cheap", "Enable ultra-cheap DeepSeek V4-Flash model ($0.07 / 1M tokens)")
        table.add_row("/model [name]", "Switch model (deepseek-v4-flash, deepseek-chat, deepseek-coder, deepseek-reasoner)")
        table.add_row("/read <file>", "Read file into chat context")
        table.add_row("/run <cmd>", "Run shell command and attach output")
        table.add_row("/search <query>", "Search project codebase")
        table.add_row("/diff", "Attach git diff")
        table.add_row("/clear", "Reset history")
        table.add_row("/exit", "Save session & exit")
        console.print(table)
        return True, None

    return False, None

def chat_command(initial_messages: Optional[List[Dict[str, str]]] = None, session_id: Optional[str] = None):
    """Token-optimized interactive chat with sliding context window."""
    print_header("AI Assistant Chat", "Token-optimized stream. Type /cheap for V4-Flash, /help for commands, /exit to quit.")
    
    info = render_project_badge()
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

            if user_input.startswith("/"):
                handled, sys_msg = handle_slash_command(user_input, history)
                if handled:
                    save_session(sess_id, history)
                    continue

            history.append({"role": "user", "content": user_input})
            
            # Sliding Context Window (keep last 6 messages to minimize input token usage)
            pruned_history = history[-6:]
            
            console.print(f"[dim]Thinking ({settings.deepseek_model})...[/dim]")
            gen = provider.stream_completion(messages=pruned_history, system_prompt=COMPACT_SYSTEM_PROMPT)
            assistant_reply, stats = stream_response(gen, console)

            history.append({"role": "assistant", "content": assistant_reply})
            save_session(sess_id, history)

            # Tool execution check
            executed, tool_out = check_and_execute_agent_tools(assistant_reply)
            if executed:
                history.append({"role": "user", "content": f"Tool Output:\n{tool_out[:2500]}"})
                pruned_history2 = history[-6:]
                gen2 = provider.stream_completion(messages=pruned_history2, system_prompt=COMPACT_SYSTEM_PROMPT)
                reply2, stats2 = stream_response(gen2, console)
                history.append({"role": "assistant", "content": reply2})
                save_session(sess_id, history)

        except (KeyboardInterrupt, EOFError):
            if history:
                save_session(sess_id, history)
                console.print(f"\n[dim]Session saved (ID: {sess_id}). Session terminated.[/dim]")
            else:
                console.print("\n[dim]Session terminated.[/dim]")
            sys.exit(0)
