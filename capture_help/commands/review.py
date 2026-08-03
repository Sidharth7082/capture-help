import sys
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

from capture_help.deepseek import get_provider
from capture_help.utils import (
    print_header,
    read_stdin_or_file,
    stream_response,
    render_project_badge,
    get_git_diff,
    copy_to_clipboard,
    export_to_markdown,
)

console = Console()

DIFF_REVIEW_PROMPT = """You are a Senior Code Reviewer performing a review on a git diff:

```diff
{content}
```

Instructions:
1. Provide an executive summary of the changes.
2. Identify potential bugs, race conditions, or breaking changes.
3. List recommendations with checkmarks ✓."""

FILE_REVIEW_PROMPT = """You are a Senior Code Reviewer.
Perform a thorough code review for file '{filename}':

```{language}
{content}
```

Instructions:
1. Evaluate code quality, readability, maintainability, and safety.
2. Identify potential bugs, security issues, and dead code.
3. Provide prioritized recommendations with checkmarks ✓."""

def review_command(
    target: Optional[str] = None,
    staged: bool = False,
    ref: Optional[str] = None,
    copy: bool = False,
    export: Optional[str] = None,
):
    """Perform an automated code review on a file, directory, or git ref (--staged, HEAD~3, origin/main)."""
    full_output = ""

    # Check git ref / staged first
    if staged or ref:
        git_ref = "--staged" if staged else ref
        diff_text = get_git_diff(git_ref)
        if not diff_text:
            console.print(f"[bold yellow]No git diff found for ref '{git_ref}'![/bold yellow]")
            return

        print_header("Automated Git Diff Review", f"Reviewing git diff ({git_ref})")
        render_project_badge()

        console.print(f"[bold cyan]Reviewing git diff '{git_ref}' ({len(diff_text.splitlines())} lines)...[/bold cyan]\n")
        provider = get_provider()
        prompt = DIFF_REVIEW_PROMPT.format(content=diff_text[:15_000])
        gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
        full_output, stats = stream_response(gen, console)

        if copy and full_output:
            copy_to_clipboard(full_output)
        if export and full_output:
            export_to_markdown(export, full_output)
        return

    # Check stdin pipe
    if not sys.stdin.isatty():
        content, _, name = read_stdin_or_file(None)
        print_header("Automated Diff Review", "Piped stdin git diff")
        render_project_badge()

        console.print(f"[bold cyan]Reviewing piped git diff ({len(content.splitlines())} lines)...[/bold cyan]\n")
        provider = get_provider()
        prompt = DIFF_REVIEW_PROMPT.format(content=content[:15_000])
        gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
        full_output, stats = stream_response(gen, console)

        if copy and full_output:
            copy_to_clipboard(full_output)
        if export and full_output:
            export_to_markdown(export, full_output)
        return

    if not target:
        target = "."

    content, path, name = read_stdin_or_file(target)
    print_header("Automated Code Review", f"Reviewing {name}")
    info = render_project_badge()

    provider = get_provider()

    if path and path.is_dir():
        from capture_help.utils import collect_directory_info
        dir_info = collect_directory_info(path)
        
        table = Table(title="📦 Project Summary", border_style="cyan", expand=True)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Details", style="bold white")
        
        table.add_row("Primary Language", dir_info["primary_language"])
        table.add_row("Total Files Analyzed", str(dir_info["total_files"]))
        table.add_row("Total Lines of Code", f"{dir_info['total_lines']:,}")
        
        lang_summary = ", ".join([f"{k} ({v})" for k, v in dir_info["languages"].items()])
        table.add_row("Language Breakdown", lang_summary or dir_info["primary_language"])
        
        console.print(table)
        console.print("\n[bold cyan]⚡ Running deep architectural review...[/bold cyan]\n")

        code_samples = ""
        sample_files = dir_info["files"][:6]
        for f in sample_files:
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fo:
                    sample_text = fo.read(3000)
                    code_samples += f"\n--- File: {f.name} ---\n{sample_text}\n"
            except Exception:
                pass

        prompt = (
            f"Perform an architectural code review for project '{info['name']}'.\n"
            f"Languages: {', '.join(info['languages'])}\n"
            f"Build System: {', '.join(info['build_systems'])}\n"
            f"Code Samples:\n{code_samples[:15_000]}\n"
            f"Instructions:\n1. Executive architectural review.\n2. Potential bugs & security smells.\n3. Prioritized recommendations with checkmarks ✓."
        )
        gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
        full_output, stats = stream_response(gen, console)
    else:
        lang = path.suffix.lstrip(".") if path else "text"
        prompt = FILE_REVIEW_PROMPT.format(filename=name, language=lang, content=content[:20_000])
        gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
        full_output, stats = stream_response(gen, console)

    if copy and full_output:
        copy_to_clipboard(full_output)
    if export and full_output:
        export_to_markdown(export, full_output)
