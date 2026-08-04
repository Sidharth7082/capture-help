import os
import stat
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from capture_help.project import find_project_root
from capture_help.utils import print_header

console = Console()

HOOK_SCRIPT = """#!/bin/bash
# capture-help Git Pre-Commit Security Hook
echo "⚡ Running capture-help pre-commit security review..."
OUTPUT=$(capture-help review --staged 2>&1)
RESULT=$?
echo "$OUTPUT"

if [ $RESULT -eq 0 ]; then
    exit 0
fi

# Only block the commit on a genuine review failure. Operational problems
# (offline, missing API key, provider/network errors, model not found) must
# never block commits — a reviewer outage is not a security finding.
if echo "$OUTPUT" | grep -qiE "API Error|Ollama Error|Network Error|not found|connect|authentication|401|403|api key|timed out"; then
    echo ""
    echo "⚠️  capture-help review could not reach its AI provider (operational error, not a security finding)."
    echo "    Commit proceeding. Run 'capture-help review --staged' manually to see the full review."
    exit 0
fi

echo "❌ capture-help review detected critical issues. Commit aborted."
exit 1
"""

def hook_command(action: str = "install"):
    """Install or uninstall Git pre-commit security review hook."""
    print_header("Git Pre-Commit Hook Manager")

    root = find_project_root()
    git_dir = root / ".git"

    if not git_dir.exists():
        console.print(f"[bold red]Error:[/bold red] '{root.name}' is not a Git repository.")
        return

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_commit = hooks_dir / "pre-commit"

    if action.lower() == "uninstall":
        if pre_commit.exists():
            pre_commit.unlink()
            console.print(f"[bold green]✓ Pre-commit hook removed from {pre_commit}[/bold green]")
        else:
            console.print("[dim]No pre-commit hook installed.[/dim]")
        return

    # Install hook
    with open(pre_commit, "w", encoding="utf-8") as f:
        f.write(HOOK_SCRIPT)

    # Make executable
    st = os.stat(pre_commit)
    os.chmod(pre_commit, st.st_mode | stat.S_IEXEC)

    console.print(Panel(
        f"[bold green]✓ Successfully installed Git Pre-Commit Security Hook![/bold green]\n"
        f"Location: [bold white]{pre_commit}[/bold white]\n"
        f"Every `git commit` will now run `capture-help review --staged` automatically.",
        border_style="green",
        expand=False
    ))
