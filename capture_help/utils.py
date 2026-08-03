import os
import sys
import re
import shutil
import difflib
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Generator, Any

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.markdown import Markdown
from rich.theme import Theme
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table

from capture_help.project import fingerprint_project, find_project_root

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "brand": "bold cyan",
})

console = Console(theme=custom_theme)

def get_console() -> Console:
    return console

def print_header(title: str, subtitle: Optional[str] = None):
    from capture_help import __version__
    text = f"[bold cyan]⚡ capture-help v{__version__}[/bold cyan] │ [bold white]{title}[/bold white]"
    if subtitle:
        text += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(text, border_style="cyan", expand=False))

def render_project_badge() -> Dict[str, Any]:
    info = fingerprint_project()
    langs_str = ", ".join(info["languages"]) if info["languages"] else "Generic"
    build_str = ", ".join(info["build_systems"]) if info["build_systems"] else "N/A"
    git_str = "[green]Clean[/green]" if info["git_clean"] else "[yellow]Modified[/yellow]"

    badge = (
        f"[bold cyan]🧠 Project Intelligence:[/bold cyan] "
        f"[bold white]{info['name']}[/bold white] │ "
        f"Langs: [yellow]{langs_str}[/yellow] │ "
        f"Build: [green]{build_str}[/green] │ "
        f"Git: {git_str}"
    )
    console.print(Panel(badge, border_style="dim white", expand=False))
    return info

def read_stdin_or_file(filepath_or_arg: Optional[str] = None, max_bytes: int = 500_000) -> Tuple[str, Optional[Path], str]:
    if not sys.stdin.isatty():
        try:
            content = sys.stdin.read(max_bytes)
            return content, None, "stdin"
        except Exception as e:
            console.print(f"[bold red]Error reading stdin:[/bold red] {e}")
            sys.exit(1)

    if filepath_or_arg:
        path = Path(filepath_or_arg).expanduser().resolve()
        if not path.exists():
            console.print(f"[bold red]Error:[/bold red] File not found: [yellow]{filepath_or_arg}[/yellow]")
            sys.exit(1)
        if path.is_dir():
            return "", path, path.name

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            return content, path, path.name
        except Exception as e:
            console.print(f"[bold red]Error reading file {filepath_or_arg}:[/bold red] {e}")
            sys.exit(1)

    console.print("[bold red]Error:[/bold red] No file path provided and stdin is empty.")
    sys.exit(1)

def is_build_log(path: Optional[Path], content: str) -> bool:
    if path and path.suffix in [".log", ".out", ".err", ".txt"]:
        if "log" in path.name.lower() or "build" in path.name.lower() or "make" in path.name.lower():
            return True

    log_indicators = [
        r"error:", r"fatal error:", r"undefined reference to",
        r"npm ERR!", r"Traceback \(most recent call last\):",
        r"FAILED:", r"ninja: build stopped", r"make: \*\*\* \[",
        r"\[ERROR\]", r"panic:", r"exception in thread", r"syntaxerror:"
    ]
    matches = sum(1 for pattern in log_indicators if re.search(pattern, content, re.IGNORECASE))
    return matches >= 2 or (path and path.suffix in [".log", ".out"] and matches >= 1)

def extract_log_summary(content: str) -> Dict[str, Any]:
    lines = content.splitlines()
    error_lines = [line for line in lines if re.search(r"\b(error|fatal error|FAILED|npm ERR!|Traceback)\b", line, re.IGNORECASE)]
    warning_lines = [line for line in lines if re.search(r"\bwarning\b", line, re.IGNORECASE)]
    return {
        "error_count": len(error_lines),
        "warning_count": len(warning_lines),
        "total_lines": len(lines),
    }

def get_git_diff(ref: Optional[str] = None) -> str:
    """Fetch git diff supporting ref flags (--staged, HEAD~3, origin/main)."""
    try:
        cmd = ["git", "diff"]
        if ref:
            cmd.extend(ref.split())
        else:
            # Default fallback try staged then unstaged
            res = subprocess.run(["git", "diff", "--staged"], capture_output=True, text=True, check=True)
            diff = res.stdout.strip()
            if diff:
                return diff

        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return ""

def stream_response(generator: Generator[Tuple[str, Any], None, None], console_obj: Optional[Console] = None) -> Tuple[str, Any]:
    """Stream LLM response with real-time Rich Markdown rendering and Ctrl+C cancellation."""
    con = console_obj or console
    full_text = ""
    stats = None

    try:
        with Live(Markdown(""), console=con, refresh_per_second=12) as live:
            for chunk, usage_stats in generator:
                if chunk:
                    full_text += chunk
                    live.update(Markdown(full_text))
                if usage_stats:
                    stats = usage_stats
    except KeyboardInterrupt:
        con.print("\n[bold yellow]⏹ Generation cancelled by user (Ctrl+C).[/bold yellow]")

    if stats:
        print_token_usage(stats)

    return full_text, stats

def print_token_usage(stats: Any):
    if not stats:
        return
    text = (
        f"⚡ [dim]Time: [white]{stats.duration_seconds:.1f}s[/white] │ "
        f"Tokens: [white]{stats.total_tokens:,}[/white] (in: {stats.prompt_tokens}, out: {stats.completion_tokens}) │ "
        f"Cost: [bold green]~${stats.cost_usd:.5f}[/bold green] │ "
        f"Model: [white]{stats.model}[/white][/dim]"
    )
    console.print(Panel(text, border_style="dim cyan", expand=False))

def prompt_apply_patch(filepath: Path, original_code: str, new_code: str):
    if original_code.strip() == new_code.strip():
        console.print("[dim]No changes detected in suggested fix.[/dim]")
        return

    diff_lines = list(difflib.unified_diff(
        original_code.splitlines(keepends=True),
        new_code.splitlines(keepends=True),
        fromfile=f"a/{filepath.name}",
        tofile=f"b/{filepath.name}",
    ))
    diff_text = "".join(diff_lines)

    console.print("\n[bold cyan]🔍 Proposed Diff:[/bold cyan]")
    console.print(Syntax(diff_text, "diff", theme="monokai", line_numbers=True))

    if Confirm.ask(f"\n[bold yellow]Apply this change to {filepath.name}?[/bold yellow]", default=False):
        backup_path = filepath.with_suffix(filepath.suffix + ".bak")
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(original_code)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_code)

        console.print(f"[bold green]✓ File updated successfully![/bold green] (Backup created at [dim]{backup_path.name}[/dim])")
    else:
        console.print("[dim]Patch skipped.[/dim]")

def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard."""
    for tool in ["wl-copy", "xclip", "xsel", "pbcopy"]:
        if shutil.which(tool):
            try:
                cmd = [tool]
                if tool == "xclip":
                    cmd.extend(["-selection", "clipboard"])
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                p.communicate(input=text.encode("utf-8"))
                console.print("[bold green]✓ Output copied to system clipboard![/bold green]")
                return True
            except Exception:
                pass
    console.print("[bold yellow]! Clipboard utility not found (install wl-clipboard or xclip).[/bold yellow]")
    return False

def export_to_markdown(filepath: str, content: str):
    """Export generated output to a Markdown file."""
    path = Path(filepath).expanduser().resolve()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"[bold green]✓ Successfully exported output to:[bold white] {path}[/bold white]")
    except Exception as e:
        console.print(f"[bold red]Error exporting to {filepath}:[/bold red] {e}")
