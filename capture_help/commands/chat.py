import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, stream_response

console = Console()

CHAT_SYSTEM_PROMPT = """You are `capture-help`, an expert AI coding assistant built for the terminal.
Provide concise, accurate, clean code solutions with brief explanations. Format code blocks cleanly with syntax highlighting labels."""

def chat_command():
    """Interactive AI chat in the terminal."""
    print_header("Interactive Chat", "Type /exit or Ctrl+C to quit. Type /clear to reset history.")
    
    provider = get_provider()
    history = []

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]capture-help>[/bold cyan] ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["/exit", "exit", "quit", ":q"]:
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() in ["/clear", "clear"]:
                history = []
                console.print("[green]✓ Chat history cleared.[/green]")
                continue

            if user_input.lower() in ["/help", "help"]:
                console.print("[yellow]Commands:[/yellow]\n  /clear - Clear chat history\n  /exit  - Quit chat session\n  /help  - Show this help message")
                continue

            history.append({"role": "user", "content": user_input})
            
            console.print("[dim]Thinking...[/dim]")
            gen = provider.stream_completion(messages=history, system_prompt=CHAT_SYSTEM_PROMPT)
            assistant_reply = stream_response(gen, console)

            history.append({"role": "assistant", "content": assistant_reply})

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session terminated.[/dim]")
            sys.exit(0)
