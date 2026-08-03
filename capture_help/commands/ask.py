from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from capture_help.deepseek import get_provider
from capture_help.project import search_project_context, fingerprint_project
from capture_help.utils import print_header, render_project_badge, stream_response

console = Console()

ASK_PROMPT = """You are a senior software architect assisting with a codebase.
Project Context:
- Project Name: {project_name}
- Key Languages: {languages}
- Build System: {build_systems}

User Question: {question}

Relevant Project File Context:
{context_snippets}

Instructions:
Answer the question accurately using the project context. Cite file paths and line logic where appropriate."""

def ask_command(question: str):
    """Ask a question about the entire codebase using project indexing & search."""
    print_header("Codebase Question & Search", question)
    info = render_project_badge()

    console.print(f"[bold cyan]🔍 Indexing & searching repository context for:[/bold cyan] [white]'{question}'[/white]...\n")

    matches = search_project_context(question, top_k=4)
    context_text = ""

    if matches:
        table = Table(title="📍 Referenced Project Context Files", border_style="cyan", expand=True)
        table.add_column("File Path", style="bold yellow")
        table.add_column("Relevance Score", style="bold green")

        for file_path, text, score in matches:
            rel_path = file_path.relative_to(info["root"]) if file_path.is_relative_to(info["root"]) else file_path
            table.add_row(str(rel_path), f"{score:.2f}")
            context_text += f"\n--- File: {rel_path} ---\n{text[:4000]}\n"

        console.print(table)
        console.print()
    else:
        console.print("[dim]No direct file matches found. Answering using project metadata...[/dim]\n")

    provider = get_provider()
    prompt = ASK_PROMPT.format(
        project_name=info["name"],
        languages=", ".join(info["languages"]) or "Generic",
        build_systems=", ".join(info["build_systems"]) or "N/A",
        question=question,
        context_snippets=context_text or "No snippet matches.",
    )

    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
