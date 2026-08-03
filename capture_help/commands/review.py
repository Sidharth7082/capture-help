from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from capture_help.deepseek import get_provider
from capture_help.utils import (
    print_header,
    read_file_content,
    collect_directory_info,
    stream_response,
)

console = Console()

DIRECTORY_REVIEW_PROMPT = """You are a Principal Software Architect performing a code review on a project codebase.
Project Info:
- Primary Language: {primary_language}
- Total Files: {total_files}
- Total Lines: {total_lines}
- Sample Files Inspected: {file_names}

Code Samples:
{code_samples}

Instructions:
1. Provide an executive architectural review.
2. Highlight:
   - Potential Bugs & Race Conditions
   - Code Smells & Dead Code
   - Memory Management & Performance
   - Security & Input Sanitization
3. Conclude with a clear list of prioritized 'Recommendations' (use checkmarks ✓ for actionable items)."""

FILE_REVIEW_PROMPT = """You are a Senior Code Reviewer.
Perform a thorough code review for file '{filename}':

```{language}
{content}
```

Instructions:
1. Evaluate code quality, readability, maintainability, and safety.
2. Identify:
   - Potential Bugs & Edge Cases
   - Security & Memory Vulnerabilities
   - Performance Bottlenecks
   - Dead Code / Unused Imports
3. Provide prioritized recommendations with checkmarks ✓."""

def review_command(target_path: str):
    """Perform an automated code review on a file or entire directory."""
    path = Path(target_path).expanduser().resolve()
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] Path does not exist: [yellow]{target_path}[/yellow]")
        return

    print_header("Automated Code Review", f"Reviewing {path.name}")
    provider = get_provider()

    if path.is_dir():
        info = collect_directory_info(path)
        
        # Render beautiful Project Summary Table
        table = Table(title="📦 Project Summary", border_style="cyan", expand=True)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Details", style="bold white")
        
        table.add_row("Primary Language", info["primary_language"])
        table.add_row("Total Files Analyzed", str(info["total_files"]))
        table.add_row("Total Lines of Code", f"{info['total_lines']:,}")
        
        lang_summary = ", ".join([f"{k} ({v})" for k, v in info["languages"].items()])
        table.add_row("Language Breakdown", lang_summary or info["primary_language"])
        
        console.print(table)
        console.print("\n[bold cyan]⚡ Running deep architectural review...[/bold cyan]\n")

        # Prepare code samples from directory
        code_samples = ""
        sample_files = info["files"][:6]
        for f in sample_files:
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fo:
                    sample_text = fo.read(3000)
                    code_samples += f"\n--- File: {f.name} ---\n{sample_text}\n"
            except Exception:
                pass

        prompt = DIRECTORY_REVIEW_PROMPT.format(
            primary_language=info["primary_language"],
            total_files=info["total_files"],
            total_lines=info["total_lines"],
            file_names=", ".join([f.name for f in sample_files]),
            code_samples=code_samples[:15_000]
        )
        gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
        stream_response(gen, console)

    else:
        content, file_path = read_file_content(target_path)
        lang = file_path.suffix.lstrip(".") or "text"

        table = Table(title="📄 File Summary", border_style="cyan", expand=True)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="bold white")
        table.add_row("Filename", file_path.name)
        table.add_row("Language", lang.upper())
        table.add_row("Line Count", str(len(content.splitlines())))
        table.add_row("File Size", f"{file_path.stat().st_size / 1024:.2f} KB")
        
        console.print(table)
        console.print("\n[bold cyan]⚡ Reviewing code quality & vulnerabilities...[/bold cyan]\n")

        prompt = FILE_REVIEW_PROMPT.format(filename=file_path.name, language=lang, content=content[:20_000])
        gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
        stream_response(gen, console)
