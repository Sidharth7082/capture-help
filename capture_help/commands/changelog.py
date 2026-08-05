import subprocess
from typing import Optional
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, stream_response, export_to_markdown

console = Console()

CHANGELOG_PROMPT = """You are a Release Engineer.
Parse the following git commit log and generate a professional `CHANGELOG.md` entry:

```text
{commits}
```

Format using Conventional Commits headings:
'## 🚀 Features'
'## 🐛 Bug Fixes'
'## ⚡ Performance Improvements'
'## 📝 Documentation & Refactoring'"""

def changelog_command(export: Optional[str] = "CHANGELOG.md"):
    """Generate GitHub-style CHANGELOG.md from git commit history."""
    print_header("Automatic CHANGELOG Generator")

    try:
        res = subprocess.run(["git", "log", "-n", "30", "--oneline"], capture_output=True, text=True, check=True)
        commits = res.stdout.strip()
    except Exception as e:
        console.print(f"[bold red]Error reading git log:[/bold red] {str(e)}")
        return

    if not commits:
        console.print("[bold yellow]No git commit history found.[/bold yellow]")
        return

    console.print(f"[bold cyan]Analyzing last 30 git commits...[/bold cyan]\n")

    provider = get_provider()
    prompt = CHANGELOG_PROMPT.format(commits=commits)
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    full_output, stats = stream_response(gen, console)

    if export and full_output:
        export_to_markdown(export, full_output)
