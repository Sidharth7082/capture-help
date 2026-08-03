import sys
import uuid
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.table import Table

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.styles import Style
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False
    from rich.prompt import Prompt

from capture_help.config import settings, save_config
from capture_help.deepseek import get_provider, DEEPSEEK_MODELS
from capture_help.history import save_session
from capture_help.project import fingerprint_project
from capture_help.utils import print_header, render_project_badge, stream_response, get_git_diff
from capture_help.cache import get_cached_system_prompt, render_cache_stats
from capture_help.agent import (
    agent_read_file,
    agent_write_file,
    agent_run_command,
    agent_search_codebase,
    check_and_execute_agent_tools,
    clean_dsml_response,
)

console = Console()

# Premium Dark Mode Theme for prompt_toolkit Autocomplete Popup
POPUP_STYLE = Style.from_dict({
    # Popup menu background & text
    'completion-menu': 'bg:#11111b #cdd6f4',
    'completion-menu.completion': 'bg:#181825 #89b4fa',
    'completion-menu.completion.current': 'bg:#89b4fa #11111b bold',
    
    # Description metadata column
    'completion-menu.meta': 'bg:#1e1e2e #a6adc8',
    'completion-menu.meta.completion': 'bg:#1e1e2e #a6adc8',
    'completion-menu.meta.completion.current': 'bg:#74c7ec #11111b bold',
    
    # Prompt text styling
    'prompt': '#89b4fa bold',
})

SLASH_COMMAND_SUGGESTIONS = [
    ("/gemma", "Switch to local Google Gemma 3 12B (Q4) model (FREE / Local Ollama)"),
    ("/cheap", "Switch to ultra-cheap DeepSeek V4-Flash model ($0.07 / 1M tokens)"),
    ("/model", "View or switch active AI model"),
    ("/plan", "Create step-by-step implementation plan"),
    ("/read", "Read file content into AI chat context"),
    ("/run", "Run terminal shell command and attach output"),
    ("/search", "Search project codebase for keywords"),
    ("/diff", "Attach current git diff to chat context"),
    ("/clear", "Clear conversation history"),
    ("/help", "Show interactive slash commands menu"),
    ("/exit", "Save chat session and exit"),
]

if PROMPT_TOOLKIT_AVAILABLE:
    class SlashCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if text.startswith("/"):
                for cmd, desc in SLASH_COMMAND_SUGGESTIONS:
                    if cmd.startswith(text):
                        yield Completion(
                            cmd,
                            start_position=-len(text),
                            display=HTML(f"<bold><cyan>{cmd}</cyan></bold>"),
                            display_meta=HTML(f"<italic>{desc}</italic>")
                        )

def handle_slash_command(cmd_text: str, history: List[Dict[str, str]]) -> Tuple[bool, Optional[str]]:
    parts = cmd_text.strip().split(maxsplit=1)
    sub = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if sub == "/gemma":
        save_config(
            api_key=settings.deepseek_api_key or "ollama",
            base_url="http://localhost:11434/v1",
            model="gemma3:12b",
            provider="ollama",
        )
        console.print("[bold green]🥇 Activated Google Gemma 3 12B (Q4) Local Model![/bold green] (FREE via Ollama http://localhost:11434)")
        return True, None

    if sub == "/model":
        if not arg:
            table = Table(title="🤖 Available AI Models", border_style="cyan")
            table.add_column("Model Key", style="bold yellow")
            table.add_column("Model Name", style="bold white")
            table.add_column("Status", style="bold green")
            table.add_column("Input Cost (per 1M)", style="green")
            for key, data in DEEPSEEK_MODELS.items():
                status = "[bold green]✓ Active[/bold green]" if key == settings.deepseek_model else ""
                cost_str = "FREE (Local)" if data['input_cost_per_m'] == 0 else f"${data['input_cost_per_m']:.2f}"
                table.add_row(key, data["name"], status, cost_str)
            console.print(table)
            console.print("[dim]To switch model: [bold white]/model gemma3:12b[/bold white] or [bold white]/model deepseek-v4-flash[/bold white][/dim]")
        else:
            p_key = arg.lower().strip()
            if p_key in DEEPSEEK_MODELS:
                prov = "ollama" if "gemma" in p_key else "deepseek"
                url = "http://localhost:11434/v1" if "gemma" in p_key else settings.deepseek_base_url
                save_config(
                    api_key=settings.deepseek_api_key or "ollama",
                    base_url=url,
                    model=p_key,
                    provider=prov,
                )
                console.print(f"[bold green]✓ Switched active model to:[bold white] {DEEPSEEK_MODELS[p_key]['name']} ({p_key})[/bold white]")
            else:
                console.print(f"[bold red]Unknown model '{arg}'.[/bold red] Run `/model` to see available models.")
        return True, None

    if sub == "/cheap":
        save_config(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            provider="deepseek",
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
        table.add_row("/gemma", "Enable Google Gemma 3 12B (Q4) FREE local Ollama model")
        table.add_row("/cheap", "Enable ultra-cheap DeepSeek V4-Flash model ($0.07 / 1M tokens)")
        table.add_row("/model [name]", "Switch model (gemma3:12b, deepseek-v4-flash, deepseek-chat, deepseek-coder, deepseek-reasoner)")
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
    """Interactive AI chat with styled prompt_toolkit slash autocompletion popup."""
    print_header("AI Assistant Chat", "Type / for live autocompletion popup. Type /exit to quit.")
    
    info = render_project_badge()
    cached_system_prompt = get_cached_system_prompt(info["name"], info["languages"])

    history: List[Dict[str, str]] = initial_messages or []
    sess_id = session_id or str(uuid.uuid4())[:8]

    if history:
        console.print(f"[dim]Loaded {len(history)} previous message(s).[/dim]")

    if PROMPT_TOOLKIT_AVAILABLE:
        try:
            session = PromptSession(completer=SlashCompleter(), style=POPUP_STYLE)
        except Exception:
            session = None
    else:
        session = None

    while True:
        try:
            if session:
                user_input = session.prompt(HTML("\n<prompt>capture-help&gt; </prompt>")).strip()
            else:
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
            
            # Sliding Context Window (keep last 6 messages)
            pruned_history = history[-6:]
            
            console.print(f"[dim]Thinking ({settings.deepseek_model})...[/dim]")
            provider = get_provider()
            gen = provider.stream_completion(messages=pruned_history, system_prompt=cached_system_prompt)
            assistant_reply, stats = stream_response(gen, console)

            if stats:
                render_cache_stats(stats.cache_hit_tokens, stats.prompt_tokens)

            # Tool execution check & DSML cleanup
            executed, tool_out = check_and_execute_agent_tools(assistant_reply)
            clean_reply = clean_dsml_response(assistant_reply)

            history.append({"role": "assistant", "content": clean_reply or assistant_reply})
            save_session(sess_id, history)

            if executed:
                history.append({"role": "user", "content": f"Tool Output:\n{tool_out[:2500]}"})
                pruned_history2 = history[-6:]
                gen2 = provider.stream_completion(messages=pruned_history2, system_prompt=cached_system_prompt)
                reply2, stats2 = stream_response(gen2, console)
                if stats2:
                    render_cache_stats(stats2.cache_hit_tokens, stats2.prompt_tokens)
                history.append({"role": "assistant", "content": clean_dsml_response(reply2)})
                save_session(sess_id, history)

        except (KeyboardInterrupt, EOFError):
            if history:
                save_session(sess_id, history)
                console.print(f"\n[dim]Session saved (ID: {sess_id}). Session terminated.[/dim]")
            else:
                console.print("\n[dim]Session terminated.[/dim]")
            sys.exit(0)
