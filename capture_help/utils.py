import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Generator, Any

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text
from rich.theme import Theme

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
    text = f"[bold cyan]⚡ capture-help[/bold cyan] │ [bold white]{title}[/bold white]"
    if subtitle:
        text += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(text, border_style="cyan", expand=False))

def read_file_content(filepath: str, max_bytes: int = 500_000) -> Tuple[str, Path]:
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: [yellow]{filepath}[/yellow]")
        raise FileNotFoundError(f"File not found: {filepath}")
    
    if path.is_dir():
        console.print(f"[bold red]Error:[/bold red] Path is a directory, expected a file: [yellow]{filepath}[/yellow]")
        raise IsADirectoryError(f"Path is a directory: {filepath}")

    file_size = path.stat().st_size
    if file_size > max_bytes:
        console.print(f"[yellow]Warning:[/yellow] File '{path.name}' is large ({file_size / 1024:.1f} KB). Reading first 500KB.")

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_bytes)
        return content, path
    except Exception as e:
        console.print(f"[bold red]Error reading file {filepath}:[/bold red] {e}")
        raise e

def is_build_log(path: Path, content: str) -> bool:
    """Detect if file is a build log or log file."""
    if path.suffix in [".log", ".out", ".err", ".txt"]:
        if "log" in path.name.lower() or "build" in path.name.lower() or "make" in path.name.lower():
            return True

    log_indicators = [
        r"error:", r"fatal error:", r"undefined reference to",
        r"npm ERR!", r"Traceback \(most recent call last\):",
        r"FAILED:", r"ninja: build stopped", r"make: \*\*\* \[",
        r"\[ERROR\]", r"panic:", r"exception in thread", r"syntaxerror:"
    ]
    matches = 0
    for pattern in log_indicators:
        if re.search(pattern, content, re.IGNORECASE):
            matches += 1

    return matches >= 2 or (path.suffix in [".log", ".out"] and matches >= 1)

def extract_log_summary(content: str) -> Dict[str, Any]:
    """Extract compiler errors and warnings summary from build logs."""
    lines = content.splitlines()
    error_lines = []
    warning_lines = []
    
    for i, line in enumerate(lines):
        if re.search(r"\b(error|fatal error|FAILED|npm ERR!|Traceback)\b", line, re.IGNORECASE):
            # Grab context (up to 3 lines)
            ctx = "\n".join(lines[max(0, i-1):min(len(lines), i+3)])
            error_lines.append(ctx)
        elif re.search(r"\bwarning\b", line, re.IGNORECASE):
            warning_lines.append(line)

    return {
        "error_count": len(error_lines),
        "warning_count": len(warning_lines),
        "error_snippets": error_lines[:5],
        "warning_snippets": warning_lines[:5],
        "total_lines": len(lines),
    }

def get_git_diff() -> str:
    """Fetch git diff (staged or unstaged) from current git repository."""
    try:
        # Try staged diff first
        res = subprocess.run(["git", "diff", "--staged"], capture_output=True, text=True, check=True)
        diff = res.stdout.strip()
        
        if not diff:
            # Try unstaged diff
            res = subprocess.run(["git", "diff"], capture_output=True, text=True, check=True)
            diff = res.stdout.strip()

        if not diff:
            # Try untracked status if no diff
            res = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, check=True)
            diff = res.stdout.strip()

        return diff
    except subprocess.CalledProcessError:
        return ""
    except FileNotFoundError:
        return ""

def collect_directory_info(target_dir: Path) -> Dict[str, Any]:
    """Scan directory to collect code metrics for capture-help review."""
    lang_extensions = {
        ".cpp": "C++", ".hpp": "C++", ".c": "C", ".h": "C/C++",
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".jsx": "React JSX", ".tsx": "React TSX", ".rs": "Rust",
        ".go": "Go", ".java": "Java", ".qml": "Qt QML",
        ".sh": "Shell", ".bash": "Shell", ".css": "CSS", ".html": "HTML"
    }

    lang_counts: Dict[str, int] = {}
    file_list: List[Path] = []
    total_files = 0
    total_lines = 0

    ignore_dirs = {".git", "venv", ".venv", "node_modules", "build", "dist", "__pycache__", ".cache"}

    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            p = Path(root) / f
            ext = p.suffix.lower()
            if ext in lang_extensions:
                lang = lang_extensions[ext]
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
                file_list.append(p)
                total_files += 1
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as file_obj:
                        total_lines += sum(1 for _ in file_obj)
                except Exception:
                    pass

    primary_lang = max(lang_counts, key=lang_counts.get) if lang_counts else "Unknown"
    return {
        "primary_language": primary_lang,
        "languages": lang_counts,
        "total_files": total_files,
        "total_lines": total_lines,
        "files": file_list[:20],  # Sample of up to 20 files
    }

def stream_response(generator: Generator[str, None, None], console_obj: Optional[Console] = None):
    """Stream LLM response with real-time Rich Markdown rendering."""
    con = console_obj or console
    full_text = ""
    with Live(Markdown(""), console=con, refresh_per_second=12) as live:
        for chunk in generator:
            full_text += chunk
            live.update(Markdown(full_text))
    return full_text
