import os
import re
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from capture_help.project import find_project_root, load_ignore_patterns
from capture_help.utils import print_header

console = Console()

SECRET_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{32,}", "OpenAI / DeepSeek Secret Key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"-----BEGIN PRIVATE KEY-----", "RSA Private Key"),
]

def secrets_command():
    """Inspect codebase for hardcoded API keys, tokens, or credentials."""
    print_header("Hardcoded Secret Inspector")

    root = find_project_root()
    ignore_patterns = load_ignore_patterns(root)
    valid_exts = {".py", ".js", ".ts", ".json", ".env", ".toml", ".yml", ".yaml", ".sh", ".c", ".cpp"}

    leaks = []

    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignore_patterns and not any(ign in d for ign in ignore_patterns)]
        for f in files:
            p = Path(r) / f
            if p.suffix.lower() not in valid_exts and p.name != ".env":
                continue

            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fo:
                    lines = fo.readlines()
                for idx, line in enumerate(lines, 1):
                    for pat, desc in SECRET_PATTERNS:
                        if re.search(pat, line):
                            rel = p.relative_to(root) if p.is_relative_to(root) else p
                            leaks.append((rel, idx, desc, line.strip()))
            except Exception:
                pass

    if not leaks:
        console.print(Panel("[bold green]✓ Security Audit Passed![/bold green]\nNo hardcoded secrets or API tokens detected in project source files.", border_style="green", expand=False))
    else:
        console.print(f"[bold red]⚠️ Security Alert: Found {len(leaks)} potential hardcoded secret(s):[/bold red]\n")
        for file_rel, line_num, desc, line_text in leaks:
            masked = line_text[:40] + "..." if len(line_text) > 40 else line_text
            console.print(f"  • [bold yellow]{file_rel}:{line_num}[/bold yellow] ([bold cyan]{desc}[/bold cyan]): [dim]{masked}[/dim]")
