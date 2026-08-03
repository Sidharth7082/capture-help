import urllib.request
import urllib.parse
import json
from rich.console import Console
from rich.panel import Panel

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, stream_response

console = Console()

WEB_PROMPT = """You are a technical web documentation specialist.
Answer the user's query using up-to-date web knowledge & best practices for:
'{query}'

Provide crisp, production-grade code examples and framework guidance."""

def web_command(query: str):
    """Fetch documentation and answer technical questions using live web context."""
    print_header("Web Search & Documentation", query)
    console.print(f"[bold cyan]🌐 Searching web & docs for:[/bold cyan] [bold white]'{query}'[/bold white]...\n")

    provider = get_provider()
    prompt = WEB_PROMPT.format(query=query)
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
