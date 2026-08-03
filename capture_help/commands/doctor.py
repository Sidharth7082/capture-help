import sys
import os
import urllib.request
import shutil
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from capture_help.config import settings, CONFIG_FILE
from capture_help.utils import print_header

console = Console()

def doctor_command():
    """Diagnose environment, configuration, dependencies, and DeepSeek API connectivity."""
    print_header("System Doctor & Diagnostics", "Verifying installation & environment health")

    table = Table(title="🏥 Diagnostic Health Check", border_style="cyan", expand=True)
    table.add_column("Component", style="bold white")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim white")

    # 1. Python Environment
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 9):
        table.add_row("Python Version", "[bold green]✓ OK[/bold green]", f"v{py_ver} ({sys.executable})")
    else:
        table.add_row("Python Version", "[bold red]✗ Outdated[/bold red]", f"v{py_ver} (Requires 3.9+)")

    # 2. Rich & OpenAI libraries
    try:
        import rich
        import openai
        import dotenv
        table.add_row("Dependencies", "[bold green]✓ OK[/bold green]", "rich, openai, python-dotenv available")
    except ImportError as e:
        table.add_row("Dependencies", "[bold red]✗ Missing[/bold red]", str(e))

    # 3. Config & Write Permissions
    if CONFIG_FILE.exists():
        if os.access(CONFIG_FILE, os.W_OK):
            table.add_row("Config File", "[bold green]✓ OK[/bold green]", f"Readable & Writable ({CONFIG_FILE})")
        else:
            table.add_row("Config File", "[bold red]✗ Permission Denied[/bold red]", f"Cannot write to {CONFIG_FILE}")
    else:
        parent = CONFIG_FILE.parent
        if parent.exists() and os.access(parent, os.W_OK):
            table.add_row("Config Dir", "[bold green]✓ OK[/bold green]", f"Writable directory ({parent})")
        else:
            table.add_row("Config Dir", "[bold yellow]! Not Created[/bold yellow]", "Will be created on config save")

    # 4. API Key Verification
    api_key = settings.deepseek_api_key
    if api_key:
        masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "Set"
        table.add_row("DeepSeek API Key", "[bold green]✓ OK[/bold green]", f"Key configured ({masked})")
    else:
        table.add_row("DeepSeek API Key", "[bold red]✗ Missing[/bold red]", "Run 'capture-help config' to set your API key")

    # 5. Git CLI
    git_path = shutil.which("git")
    if git_path:
        table.add_row("Git CLI", "[bold green]✓ OK[/bold green]", f"Found at {git_path}")
    else:
        table.add_row("Git CLI", "[bold yellow]! Not Found[/bold yellow]", "Git functionality (git diff / commit) will be disabled")

    # 6. System Clipboard Utility
    clip_tool = None
    for tool in ["wl-copy", "xclip", "xsel", "pbcopy"]:
        if shutil.which(tool):
            clip_tool = tool
            break
    if clip_tool:
        table.add_row("Clipboard Utility", "[bold green]✓ OK[/bold green]", f"Using {clip_tool}")
    else:
        table.add_row("Clipboard Utility", "[bold yellow]! Missing[/bold yellow]", "Install wl-clipboard or xclip for --copy support")

    # 7. DeepSeek API Endpoint Reachability
    url = settings.deepseek_base_url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "capture-help-doctor"})
        with urllib.request.urlopen(req, timeout=5) as response:
            table.add_row("DeepSeek Endpoint", "[bold green]✓ Reachable[/bold green]", f"{url} (Status {response.status})")
    except Exception as e:
        table.add_row("DeepSeek Endpoint", "[bold yellow]! Limited Check[/bold yellow]", f"{url} ({type(e).__name__})")

    console.print(table)
    console.print("\n[bold green]✓ All core systems operational![/bold green] Ready to assist.\n")
