import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm

from capture_help.utils import print_header

console = Console()

ALIASES_SCRIPT = """# capture-help Shell Aliases
alias ai="capture-help"
alias aiask="capture-help ask"
alias aifix="capture-help fix"
alias aireview="capture-help review"
alias aidoc="capture-help docs"
alias aicommit="capture-help commit"
alias aiexplain="capture-help explain"
"""

def alias_command(install: bool = False):
    """Generate or install shell aliases (ai, aifix, aireview, aidoc, aicommit, aiask)."""
    print_header("Shell Integration & Aliases")

    console.print(Panel("Useful Shell Aliases for Faster Terminal Access", border_style="cyan", expand=False))
    console.print(Syntax(ALIASES_SCRIPT, "bash", theme="monokai"))

    if not install:
        console.print("\n[dim]To install these aliases automatically, run:[bold white] capture-help alias --install[/bold white] or copy the block above into your ~/.bashrc or ~/.zshrc.[/dim]")
        return

    # Install to ~/.bashrc and ~/.zshrc if they exist
    home = Path.home()
    target_files = [home / ".bashrc", home / ".zshrc"]
    updated = []

    for rc_file in target_files:
        if rc_file.exists():
            content = rc_file.read_text(encoding="utf-8", errors="ignore")
            if "# capture-help Shell Aliases" not in content:
                with open(rc_file, "a", encoding="utf-8") as f:
                    f.write("\n" + ALIASES_SCRIPT)
                updated.append(rc_file.name)

    if updated:
        console.print(f"\n[bold green]✓ Successfully appended aliases to:[/bold green] [white]{', '.join(updated)}[/white]")
        console.print("[yellow]Run 'source ~/.bashrc' (or restart your terminal) to activate the new aliases![/yellow]")
    else:
        console.print("\n[dim]Aliases are already installed in your shell configuration files.[/dim]")
