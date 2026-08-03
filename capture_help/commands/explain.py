from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from capture_help.deepseek import get_provider
from capture_help.utils import (
    print_header,
    read_stdin_or_file,
    is_build_log,
    extract_log_summary,
    stream_response,
    render_project_badge,
)

console = Console()

EXPLAIN_LOG_PROMPT = """You are an expert compiler and build system diagnostic AI.
The user provided a build log / compiler output log.
Extracted Log Snippets:
{content}

Instructions:
1. Identify the EXACT compiler / runtime error and the root cause file & line number if present.
2. Explain the root cause in plain, simple English (avoid vague jargon).
3. Provide precise, actionable steps or code snippet fixes to resolve the build failure.
Format with Markdown headings: '## 🔍 Root Cause', '## 🛠️ Actionable Fix', '## 💡 Key Takeaway'."""

EXPLAIN_CODE_PROMPT = """You are an expert software developer.
Analyze the following source code ('{filename}'):

```{language}
{content}
```

Instructions:
1. Explain what this file/code does in 2-3 sentences.
2. Breakdown key components, classes, and logic.
3. Highlight notable patterns, design decisions, or external dependencies."""

def explain_command(target: Optional[str] = None):
    """Explain a file or piped stdin build log in plain English."""
    content, path, name = read_stdin_or_file(target)
    print_header("Code & Log Explainer", f"Analyzing {name}")

    provider = get_provider()

    if is_build_log(path, content):
        summary = extract_log_summary(content)
        
        table = Table(title="📋 Build Log Diagnostic Overview", border_style="yellow", expand=True)
        table.add_column("Property", style="bold cyan")
        table.add_column("Value", style="bold white")
        table.add_row("Source", name)
        table.add_row("Total Log Lines", str(summary["total_lines"]))
        table.add_row("Detected Errors", f"[bold red]{summary['error_count']}[/bold red]")
        table.add_row("Detected Warnings", f"[bold yellow]{summary['warning_count']}[/bold yellow]")
        
        console.print(table)
        console.print("\n[bold yellow]⚡ Extracting root causes and analyzing build errors...[/bold yellow]\n")

        prompt = EXPLAIN_LOG_PROMPT.format(content=content[:15_000])
        gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
        stream_response(gen, console)
    else:
        render_project_badge()
        lang = path.suffix.lstrip(".") if path else "text"
        console.print(f"[bold cyan]Source:[bold white] {name} ({len(content.splitlines())} lines)[/bold white]\n")

        prompt = EXPLAIN_CODE_PROMPT.format(filename=name, language=lang, content=content[:20_000])
        gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
        stream_response(gen, console)
