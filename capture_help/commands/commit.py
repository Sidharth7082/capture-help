import sys
from typing import Optional
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, get_git_diff, stream_response, render_project_badge

console = Console()

COMMIT_PROMPT = """You are a Git commit message expert following Conventional Commits specification (feat:, fix:, docs:, refactor:, perf:, test:, chore:).
Analyze the following git diff output:

```diff
{diff}
```

Instructions:
1. Write a single-line summary (under 72 chars) starting with a conventional type (e.g. `feat: ...` or `fix: ...`).
2. Provide a short bulleted list of key changes.
3. Provide a ready-to-copy `git commit -m "..."` command snippet."""

def commit_command():
    """Read git diff or stdin and generate a Conventional Commit message."""
    print_header("Git Commit Helper", "Analyzing staged / unstaged repository changes")

    diff = ""
    if not sys.stdin.isatty():
        diff = sys.stdin.read(100_000)
    else:
        diff = get_git_diff()

    if not diff:
        console.print("[bold yellow]No git changes detected![/bold yellow]\nMake sure you are inside a Git repo with staged or unstaged changes (`git diff` or `git status`).")
        return

    render_project_badge()
    console.print(f"[bold cyan]Detected git changes ({len(diff.splitlines())} diff lines). Generating commit message...[/bold cyan]\n")

    provider = get_provider()
    prompt = COMMIT_PROMPT.format(diff=diff[:15_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
