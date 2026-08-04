import sys
import uuid
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich import box

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
    ("/flash", "Switch to ultra-fast DeepSeek V4-Flash model"),
    ("/coder", "Switch to DeepSeek Coder model"),
    ("/r1", "Switch to DeepSeek Reasoner R1 model"),
    ("/model", "View or switch active AI model"),
    ("/persona", "Switch active character persona (e.g. /persona 1, /persona gehrman, /persona reset)"),
    ("/gehrman", "1-click shortcut to activate Gehrman Sparrow persona"),
    ("/character", "Alias for /persona character card switcher"),
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
            if text.startswith("/persona ") or text.startswith("/character "):
                prefix, *rest = text.split(maxsplit=1)
                sub_text = rest[0] if rest else ""
                from capture_help import persona as persona_mod
                options = [("list", "List available character personas"), ("reset", "Reset back to default AI Assistant")]
                for p in persona_mod.list_personas():
                    options.append((p.name, f"{p.display_name} — {p.description[:40]}"))
                for opt, desc in options:
                    if opt.startswith(sub_text):
                        full_cmd = f"{prefix} {opt}"
                        yield Completion(
                            full_cmd,
                            start_position=-len(text),
                            display=HTML(f"<bold><cyan>{full_cmd}</cyan></bold>"),
                            display_meta=HTML(f"<italic>{desc}</italic>")
                        )
            elif text.startswith("/"):
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

    if sub in ["/scan", "/virus"]:
        from capture_help.commands.scan import scan_command
        scan_command()
        return True, None

    if sub in ["/gehrman", "/sparrow"]:
        from capture_help import persona as persona_mod
        p = persona_mod.activate_persona("gehrman")
        console.print(f"[bold green]{persona_mod.render_banner(p)}[/bold green]")
        return True, None

    if sub in ["/persona", "/character"]:
        from capture_help import persona as persona_mod
        from capture_help.tui_selector import SelectOption, run_tui_selector

        personas = persona_mod.list_personas()
        active = persona_mod.get_active_persona()
        active_name = active.name if active else None

        if not arg:
            options = [
                SelectOption(
                    key="default",
                    title="Standard AI Assistant",
                    description="Default terminal coding & system administration assistant.",
                    badge="[Default]",
                    is_current=(active_name is None),
                )
            ]
            for p in personas:
                options.append(
                    SelectOption(
                        key=p.name,
                        title=p.display_name,
                        description=p.description or p.greeting or "Custom character persona card",
                        badge="[Character Card]",
                        is_current=(active_name == p.name),
                    )
                )

            chosen = run_tui_selector("Select Character Persona", options)
            if not chosen:
                return True, None
            if chosen.key == "default":
                persona_mod.reset_persona()
                console.print("[bold green]✓ Persona reset to default AI Assistant.[/bold green]")
                return True, None
            else:
                p = persona_mod.activate_persona(chosen.key)
                console.print(f"[bold green]{persona_mod.render_banner(p)}[/bold green]")
                return True, None

        if arg.strip().isdigit():
            num = int(arg.strip())
            if num == 0:
                persona_mod.reset_persona()
                console.print("[bold green]✓ Persona reset to default AI Assistant.[/bold green]")
                return True, None
            elif 1 <= num <= len(personas):
                p = persona_mod.activate_persona(personas[num - 1].name)
                console.print(f"[bold green]{persona_mod.render_banner(p)}[/bold green]")
                return True, None

        if arg.strip() in ["reset", "default"]:
            persona_mod.reset_persona()
            console.print("[bold green]✓ Persona reset to default AI Assistant.[/bold green]")
        else:
            try:
                p = persona_mod.activate_persona(arg.strip())
                console.print(f"[bold green]{persona_mod.render_banner(p)}[/bold green]")
            except persona_mod.PersonaError as e:
                console.print(f"[bold red]{e}[/bold red]")
        return True, None

    if sub in ["/learn", "/memory"]:
        from capture_help.memory import add_memory, get_all_memories
        if arg:
            add_memory("user_preference", arg)
            console.print(f"[bold green]✓ Learned new background rule:[/bold green] [bold white]{arg}[/bold white]")
        else:
            memories = get_all_memories()
            if not memories:
                console.print("[yellow]No background memories saved.[/yellow]")
            else:
                console.print(f"[bold cyan]🧠 Active Learned Rules ({len(memories)}):[/bold cyan]")
                for m in memories:
                    console.print(f"  • [white]{m['content']}[/white]")
        return True, None

    if sub in ["/gemma", "/gemma12b"]:
        save_config(api_key=settings.deepseek_api_key, base_url="http://localhost:11434/v1", model="gemma3:12b", provider="ollama")
        console.print("[bold green]🥇 Activated Google Gemma 3 12B Local Model! (FREE via Ollama)[/bold green]")
        return True, None

    if sub in ["/gemma27b"]:
        save_config(api_key=settings.deepseek_api_key, base_url="http://localhost:11434/v1", model="gemma3:27b", provider="ollama")
        console.print("[bold green]🥈 Activated Google Gemma 3 27B Local Model![/bold green]")
        return True, None

    if sub in ["/flash", "/cheap"]:
        save_config(api_key=settings.deepseek_api_key, base_url="https://api.deepseek.com", model="deepseek-v4-flash", provider="deepseek")
        console.print("[bold green]⚡ Activated DeepSeek V4-Flash Model![/bold green]")
        return True, None

    if sub in ["/coder"]:
        save_config(api_key=settings.deepseek_api_key, base_url="https://api.deepseek.com", model="deepseek-coder", provider="deepseek")
        console.print("[bold green]💻 Activated DeepSeek Coder Model![/bold green]")
        return True, None

    if sub in ["/r1", "/reasoner"]:
        save_config(api_key=settings.deepseek_api_key, base_url="https://api.deepseek.com", model="deepseek-reasoner", provider="deepseek")
        console.print("[bold green]🧠 Activated DeepSeek Reasoner R1 Model![/bold green]")
        return True, None

    if sub == "/model":
        if not arg:
            from capture_help.tui_selector import SelectOption, run_tui_selector
            options = []
            for key, data in DEEPSEEK_MODELS.items():
                cost_str = "FREE (Local)" if data['input_cost_per_m'] == 0 else f"${data['input_cost_per_m']:.2f}/1M"
                options.append(
                    SelectOption(
                        key=key,
                        title=data["name"],
                        description=f"{data['description']} | Provider: {data.get('provider', 'cloud')}",
                        badge=cost_str,
                        is_current=(key == settings.deepseek_model),
                    )
                )
            chosen = run_tui_selector("Select AI Model", options)
            if not chosen:
                return True, None
            p_key = chosen.key
            prov = "ollama" if "gemma" in p_key else "deepseek"
            url = "http://localhost:11434/v1" if "gemma" in p_key else "https://api.deepseek.com"

            if prov == "deepseek" and (not settings.deepseek_api_key or len(settings.deepseek_api_key) < 10):
                console.print(f"\n[bold yellow]⚠️ '{DEEPSEEK_MODELS[p_key]['name']}' is a Cloud AI model requiring a DeepSeek API key.[/bold yellow]")
                console.print("[dim]Set your key in terminal with: [bold white]capture-help key sk-xxxx[/bold white][/dim]")
                console.print("[bold green]🥇 Remaining on 100% FREE Local Google Gemma 3 12B model![/bold green]\n")
                p_key = "gemma3:12b"
                prov = "ollama"
                url = "http://localhost:11434/v1"

            save_config(api_key=settings.deepseek_api_key or "ollama", base_url=url, model=p_key, provider=prov)
            console.print(f"[bold green]✓ Activated model:[bold white] {DEEPSEEK_MODELS[p_key]['name']} ({p_key})[/bold white]")
            return True, None
        else:
            p_key = arg.lower().strip()
            if p_key in DEEPSEEK_MODELS:
                prov = "ollama" if "gemma" in p_key else "deepseek"
                url = "http://localhost:11434/v1" if "gemma" in p_key else settings.deepseek_base_url
                if prov == "deepseek" and (not settings.deepseek_api_key or len(settings.deepseek_api_key) < 10):
                    console.print(f"\n[bold yellow]⚠️ '{DEEPSEEK_MODELS[p_key]['name']}' is a Cloud AI model requiring a DeepSeek API key.[/bold yellow]")
                    console.print("[dim]Set your key in terminal with: [bold white]capture-help key sk-xxxx[/bold white][/dim]")
                    console.print("[bold green]🥇 Remaining on 100% FREE Local Google Gemma 3 12B model![/bold green]\n")
                    p_key = "gemma3:12b"
                    prov = "ollama"
                    url = "http://localhost:11434/v1"
                save_config(api_key=settings.deepseek_api_key or "ollama", base_url=url, model=p_key, provider=prov)
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
        history.append({"role": "user", "content": f"File content '{arg}':\n{content[:30_000]}"})
        return True, "File loaded into context."

    if sub == "/run":
        if not arg:
            console.print("[bold red]Usage:[/bold red] /run <command>")
            return True, None
        out = agent_run_command(arg)
        console.print(f"[bold cyan]Command Output:[/bold cyan]\n{out}")
        history.append({"role": "user", "content": f"Terminal output of `{arg}`:\n{out[:20_000]}"})
        return True, "Command output added."

    if sub == "/search":
        if not arg:
            console.print("[bold red]Usage:[/bold red] /search <query>")
            return True, None
        results = agent_search_codebase(arg)
        console.print(f"[bold cyan]Search Results:[/bold cyan]\n{results}")
        history.append({"role": "user", "content": f"Search results for '{arg}':\n{results[:20_000]}"})
        return True, "Search results added."

    if sub == "/diff":
        diff = get_git_diff()
        if not diff:
            console.print("[bold yellow]No git diff detected.[/bold yellow]")
        else:
            console.print(f"[bold cyan]Git Diff ({len(diff.splitlines())} lines)[/bold cyan]")
            history.append({"role": "user", "content": f"Git diff:\n```diff\n{diff[:20_000]}\n```"})
        return True, "Diff added."

    if sub in ["/help", "help"]:
        from rich import box
        table = Table(title="⚡ Slash Commands", border_style="cyan", box=box.ROUNDED)
        table.add_column("Command", style="bold yellow")
        table.add_column("Description", style="white")
        table.add_row("/gemma", "Enable Google Gemma 3 12B (Q4) FREE local Ollama model")
        table.add_row("/scan /virus", "Scan system for malware, suspicious files, and listening ports")
        table.add_row("/cheap", "Enable ultra-cheap DeepSeek V4-Flash model ($0.07 / 1M tokens)")
        table.add_row("/model [name]", "Switch model (gemma3:12b, deepseek-v4-flash, deepseek-chat, deepseek-coder)")
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

            # Sliding context window. Configurable via CAPTURE_HELP_CONTEXT_MESSAGES;
            # defaults to a generous window instead of a hard-coded 6 messages.
            # Set to 0 for unlimited context (the whole conversation).
            import os as _os
            try:
                ctx_limit = int(_os.getenv("CAPTURE_HELP_CONTEXT_MESSAGES", "30"))
            except ValueError:
                ctx_limit = 30
            pruned_history = history if ctx_limit <= 0 else history[-ctx_limit:]

            from capture_help.persona import build_system_prompt
            active_prompt = build_system_prompt(cached_system_prompt)

            try:
                provider = get_provider()
                current_prov = getattr(provider, "provider_type", settings.default_provider)
                if current_prov == "deepseek" and (not settings.deepseek_api_key or len(settings.deepseek_api_key) < 10 or "test" in settings.deepseek_api_key.lower()):
                    console.print("\n[bold yellow]⚠️ DeepSeek API Key is invalid or not set.[/bold yellow]")
                    console.print("[bold green]🥇 Automatically switching to 100% FREE Local Google Gemma 3 12B (Ollama)![/bold green]\n")
                    save_config(api_key="", provider="ollama", model="gemma3:12b")
                    provider = get_provider()
                gen = provider.stream_completion(messages=pruned_history, system_prompt=active_prompt)
                assistant_reply, stats = stream_response(gen, console)
            except Exception as e:
                err_str = str(e)
                if "401" in err_str or "Authentication" in err_str or "invalid" in err_str.lower():
                    console.print("\n[bold yellow]⚠️ DeepSeek API key authentication failed. Self-healing fallback to 100% FREE Local Google Gemma 3 12B (Ollama)...[/bold yellow]\n")
                    save_config(api_key="", provider="ollama", model="gemma3:12b")
                    provider = get_provider()
                    gen = provider.stream_completion(messages=pruned_history, system_prompt=active_prompt)
                    assistant_reply, stats = stream_response(gen, console)
                else:
                    console.print(f"[bold red]API Error:[/bold red] {err_str}")
                    continue

            if stats:
                render_cache_stats(stats.cache_hit_tokens, stats.prompt_tokens)

            # Multi-turn Autonomous Tool Execution Loop (up to 10 consecutive tool turns)
            max_tool_turns = 10
            turn_count = 0
            curr_reply = assistant_reply

            while turn_count < max_tool_turns:
                executed, tool_out = check_and_execute_agent_tools(curr_reply)
                clean_reply = clean_dsml_response(curr_reply)

                if turn_count == 0 or clean_reply:
                    history.append({"role": "assistant", "content": clean_reply or curr_reply})
                    save_session(sess_id, history)

                if not executed:
                    break

                turn_count += 1
                if turn_count >= max_tool_turns:
                    console.print("\n[dim]Reached maximum autonomous tool execution depth (10 turns).[/dim]")
                    break

                console.print(f"\n[bold cyan]🔄 [Turn {turn_count}/{max_tool_turns}] Continuing Autonomous Task Execution...[/bold cyan]")

                history.append({"role": "user", "content": f"Tool Output:\n{tool_out[:20_000]}"})
                pruned_history_loop = history if ctx_limit <= 0 else history[-ctx_limit:]

                gen_loop = provider.stream_completion(messages=pruned_history_loop, system_prompt=active_prompt)
                curr_reply, stats_loop = stream_response(gen_loop, console)
                if stats_loop:
                    render_cache_stats(stats_loop.cache_hit_tokens, stats_loop.prompt_tokens)

        except (KeyboardInterrupt, EOFError):
            if history:
                save_session(sess_id, history)
                console.print(f"\n[dim]Session saved (ID: {sess_id}). Session terminated.[/dim]")
            else:
                console.print("\n[dim]Session terminated.[/dim]")
            sys.exit(0)
