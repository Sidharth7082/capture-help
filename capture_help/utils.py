import os
import sys
import re
import shutil
import difflib
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Generator, Any

from rich.console import Console
from rich import box
from rich.panel import Panel
from rich.live import Live
from rich.markdown import Markdown
from rich.theme import Theme
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table

from capture_help.project import fingerprint_project, find_project_root, load_ignore_patterns

# MyGlass frosted palette shared with the Textual GUI (see gui/theme.py).
_BASE = "#0d1017"
_SURFACE_1 = "#12161f"
_SURFACE_2 = "#171c28"
_EDGE = "#232b3c"
_TEXT = "#e8edf4"
_MUTED = "#8f9aa9"
_ACCENT = "#63c6e2"
_SUCCESS = "#4ed98c"
_WARNING = "#e5b95c"
_ERROR = "#f2556f"

custom_theme = Theme({
    "info": _ACCENT,
    "warning": _WARNING,
    "error": f"bold {_ERROR}",
    "success": f"bold {_SUCCESS}",
    "brand": f"bold {_ACCENT}",
})

console = Console(theme=custom_theme)

def get_console() -> Console:
    return console

def collect_directory_info(directory: Path) -> Dict[str, Any]:
    """Gather language/file/line statistics for a project directory.

    Used by `capture-help review` on directory targets.
    """
    directory = directory.resolve()
    ignore_patterns = load_ignore_patterns(directory)
    lang_extensions = {
        ".cpp": "C++", ".hpp": "C++", ".c": "C", ".h": "C/C++",
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".jsx": "React JSX", ".tsx": "React TSX", ".rs": "Rust",
        ".go": "Go", ".java": "Java", ".qml": "Qt QML",
        ".lua": "Lua", ".sh": "Shell", ".css": "CSS", ".html": "HTML",
    }

    languages: Dict[str, int] = {}
    files: List[Path] = []
    total_lines = 0
    total_files = 0

    for r, dirs, names in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in ignore_patterns and not any(ign in d for ign in ignore_patterns)]
        for name in names:
            p = Path(r) / name
            ext = p.suffix.lower()
            if ext not in lang_extensions:
                continue
            files.append(p)
            total_files += 1
            lang = lang_extensions[ext]
            languages[lang] = languages.get(lang, 0) + 1
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fo:
                    total_lines += sum(1 for _ in fo)
            except Exception:
                pass

    files.sort(key=lambda p: p.name.lower())
    primary_language = max(languages, key=languages.get) if languages else "Unknown"

    return {
        "primary_language": primary_language,
        "total_files": total_files,
        "total_lines": total_lines,
        "languages": languages,
        "files": files,
    }

def print_header(title: str, subtitle: Optional[str] = None):
    from capture_help import __version__
    text = f"[bold {_ACCENT}]⚡ Capture Help[/bold {_ACCENT}]  [bold {_TEXT}]{title}[/bold {_TEXT}]  [dim]v{__version__}[/dim]"
    if subtitle:
        text += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(text, border_style=_EDGE, box=box.ROUNDED, expand=False))

def render_project_badge() -> Dict[str, Any]:
    info = fingerprint_project()
    langs_str = ", ".join(info["languages"]) if info["languages"] else "Generic"
    build_str = ", ".join(info["build_systems"]) if info["build_systems"] else "N/A"
    git_str = f"[{_SUCCESS}]✓ Clean[/{_SUCCESS}]" if info["git_clean"] else f"[{_WARNING}]✗ Modified[/{_WARNING}]"

    badge = (
        f"[{_ACCENT}]▤ Project:[/{_ACCENT}] [bold {_TEXT}]{info['name']}[/bold {_TEXT}]"
        f"   [{_ACCENT}]λ[/{_ACCENT}] [{_MUTED}]{langs_str}[/{_MUTED}]"
        f"   [{_ACCENT}]◆[/{_ACCENT}] [{_MUTED}]{build_str}[/{_MUTED}]"
        f"   [{_ACCENT}]⎇[/{_ACCENT}] {git_str}"
    )
    console.print(Panel(badge, border_style=_EDGE, box=box.ROUNDED, expand=False))
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
    from capture_help.provider import ProviderError

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
    except ProviderError:
        # Provider already printed a friendly message; exit cleanly for
        # one-shot commands instead of surfacing a raw traceback.
        raise SystemExit(1)
    except KeyboardInterrupt:
        con.print("\n[bold yellow]⏹ Generation cancelled by user (Ctrl+C).[/bold yellow]")

    if stats:
        print_token_usage(stats)

    return full_text, stats

def print_token_usage(stats: Any):
    if not stats:
        return
    text = (
        f"[{_ACCENT}]🧠[/{_ACCENT}] [{_MUTED}]{stats.model}[/{_MUTED}]"
        f"   [{_ACCENT}]▦[/{_ACCENT}] [{_MUTED}]{stats.total_tokens:,} tokens[/{_MUTED}]"
        f"   [{_ACCENT}]⏱[/{_ACCENT}] [{_MUTED}]{stats.duration_seconds:.1f}s[/{_MUTED}]"
        f"   [{_ACCENT}]¢[/{_ACCENT}] [bold {_SUCCESS}]~${stats.cost_usd:.5f}[/bold {_SUCCESS}]"
    )
    if getattr(stats, "cache_hit_tokens", 0):
        text += f"   [{_ACCENT}]⚡[/{_ACCENT}] [{_MUTED}]cache {stats.cache_hit_tokens}[/{_MUTED}]"
    console.print(text)

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
