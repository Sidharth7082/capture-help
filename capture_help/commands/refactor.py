import os
from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm

from capture_help.project import find_project_root, load_ignore_patterns
from capture_help.utils import print_header

console = Console()

def refactor_command(old_symbol: str, new_symbol: str):
    """Refactor and rename a function, variable, or class symbol across all project files."""
    print_header("Multi-File Symbol Refactor", f"Renaming '{old_symbol}' -> '{new_symbol}'")

    root = find_project_root()
    ignore_patterns = load_ignore_patterns(root)
    valid_exts = {".py", ".js", ".ts", ".cpp", ".hpp", ".c", ".h", ".qml", ".lua", ".json", ".toml", ".md"}

    modified_files = []

    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignore_patterns and not any(ign in d for ign in ignore_patterns)]
        for f in files:
            p = Path(r) / f
            if p.suffix.lower() not in valid_exts:
                continue

            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fo:
                    text = fo.read()
                if old_symbol in text:
                    modified_files.append((p, text))
            except Exception:
                pass

    if not modified_files:
        console.print(f"[bold yellow]No occurrences of symbol '{old_symbol}' found in project.[/bold yellow]")
        return

    console.print(f"[bold cyan]Found '{old_symbol}' in {len(modified_files)} file(s):[/bold cyan]")
    for p, _ in modified_files:
        rel = p.relative_to(root) if p.is_relative_to(root) else p
        console.print(f"  • [bold white]{rel}[/bold white]")

    if Confirm.ask(f"\n[bold yellow]Apply rename '{old_symbol}' -> '{new_symbol}' across {len(modified_files)} file(s)?[/bold yellow]", default=True):
        for p, text in modified_files:
            new_text = text.replace(old_symbol, new_symbol)
            with open(p, "w", encoding="utf-8") as fo:
                fo.write(new_text)
        console.print(f"[bold green]✓ Refactored '{old_symbol}' -> '{new_symbol}' across {len(modified_files)} file(s) successfully![/bold green]")
