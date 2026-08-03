from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from capture_help.deepseek import get_provider
from capture_help.project import search_project_context, fingerprint_project
from capture_help.utils import (
    print_header,
    render_project_badge,
    stream_response,
    copy_to_clipboard,
    export_to_markdown,
)

console = Console()

ASK_PROMPT = """You are a senior software architect. Answer concisely using context:
Project: {project_name} ({languages})
Question: {question}

Context Snippets:
{context_snippets}

Instructions: Provide direct, concise answer with code examples."""

def ask_command(
    question: str,
    copy: bool = False,
    export: Optional[str] = None,
):
    """Ask codebase questions with token-optimized project indexing."""
    print_header("Codebase Search", question)
    info = render_project_badge()

    console.print(f"[bold cyan]🔍 Searching project for:[/bold cyan] [white]'{question}'[/white]...\n")

    # Limit to top 2 files and 1,200 chars each to save tokens
    matches, scanned_count = search_project_context(question, top_k=2)
    context_text = ""
    total_bytes = 0

    if matches:
        table = Table(title="📍 Context Payload", border_style="cyan", expand=True)
        table.add_column("Property / File Path", style="bold yellow")
        table.add_column("Details", style="bold green")

        table.add_row("Scanned files", str(scanned_count))

        for file_path, text, score in matches:
            rel_path = file_path.relative_to(info["root"]) if file_path.is_relative_to(info["root"]) else file_path
            snippet = text[:1200]
            table.add_row(f"✓ {rel_path}", f"Relevance: {score:.2f} ({len(snippet.encode('utf-8')) / 1024:.1f} KB)")
            context_text += f"\n--- File: {rel_path} ---\n{snippet}\n"
            total_bytes += len(snippet.encode("utf-8"))

        table.add_row("Total Context Payload", f"[bold green]{total_bytes / 1024:.1f} KB[/bold green]")
        console.print(table)
        console.print()
    else:
        console.print(f"[dim]Scanned {scanned_count} files. Answering using project metadata...[/dim]\n")

    provider = get_provider()
    prompt = ASK_PROMPT.format(
        project_name=info["name"],
        languages=", ".join(info["languages"]) or "Generic",
        question=question,
        context_snippets=context_text or "No snippet matches.",
    )

    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    full_output, stats = stream_response(gen, console)

    if copy and full_output:
        copy_to_clipboard(full_output)
    if export and full_output:
        export_to_markdown(export, full_output)
