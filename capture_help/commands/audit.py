from pathlib import Path
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.project import find_project_root
from capture_help.utils import print_header, stream_response

console = Console()

AUDIT_PROMPT = """You are a DevSecOps Security Auditor.
Analyze dependency and configuration manifest for security vulnerabilities, CVE risks, and unsafe packages:

```{lang}
{content}
```

Format output with: '## 🛡️ Security Vulnerability Assessment', '## ⚠️ Recommended Dependency Upgrades', '## 🔒 Best Practices'."""

def audit_command():
    """Audit project dependencies for security vulnerabilities."""
    print_header("Security & Dependency Auditor")

    root = find_project_root()
    manifests = ["pyproject.toml", "requirements.txt", "package.json", "Cargo.toml", "CMakeLists.txt"]

    found_file = None
    content = ""
    for m in manifests:
        p = root / m
        if p.exists():
            found_file = p
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(5_000)
            break

    if not found_file:
        console.print("[bold yellow]No standard dependency manifest (pyproject.toml, package.json, Cargo.toml) found in project.[/bold yellow]")
        return

    console.print(f"[bold cyan]Auditing manifest:[/bold cyan] [bold white]{found_file.name}[/bold white]\n")

    provider = get_provider()
    prompt = AUDIT_PROMPT.format(lang=found_file.suffix.lstrip("."), content=content)
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
