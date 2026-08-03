from typing import Optional
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, get_git_diff, stream_response, copy_to_clipboard, export_to_markdown

console = Console()

PR_PROMPT = """You are a GitHub Pull Request specialist.
Read the following git diff and generate a professional GitHub Pull Request description:

```diff
{diff}
```

Format with Markdown headings:
'## 📝 Summary of Changes'
'## 🚀 Impact & Key Features'
'## ⚠️ Potential Risk & Breaking Changes'
'## 🧪 Verification & Test Checklist'"""

def pr_command(copy: bool = False, export: Optional[str] = None):
    """Generate GitHub Pull Request description from git diff."""
    print_header("GitHub PR Summarizer", "Generating PR title & release checklist")

    diff = get_git_diff()
    if not diff:
        console.print("[bold yellow]No git changes detected to generate PR for.[/bold yellow]")
        return

    console.print(f"[bold cyan]Analyzing diff ({len(diff.splitlines())} lines)...[/bold cyan]\n")

    provider = get_provider()
    prompt = PR_PROMPT.format(diff=diff[:15_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    full_output, stats = stream_response(gen, console)

    if copy and full_output:
        copy_to_clipboard(full_output)
    if export and full_output:
        export_to_markdown(export, full_output)
