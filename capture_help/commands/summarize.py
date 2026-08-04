import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.project import find_project_root, load_ignore_patterns, fingerprint_project
from capture_help.utils import (
    print_header,
    render_project_badge,
    stream_response,
    get_git_diff,
    copy_to_clipboard,
    export_to_markdown,
)

console = Console()

SUMMARIZE_PROMPT = """You are a precise technical summarizer.
Produce a concise, well-structured Markdown summary of the {kind} below.

```text
{content}
```

Instructions:
1. Start with a 1-sentence TL;DR of what this is about.
2. Use a short bulleted list of the most important points (max 8 bullets).
3. If relevant, end with a short "## Next Steps" or "## Key Risks" section.
4. Be factual and specific: keep names, paths, error codes, and numbers intact.
5. Do NOT invent details that are not present in the input."""

MAX_SUMMARY_BYTES = 50_000


def _walk_code_files(root: Path, ignore_patterns, limit: int = 400) -> list:
    """Return a list of (relative_path, size_bytes) for code-like files under root."""
    valid_exts = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".cpp", ".hpp", ".c", ".h",
        ".rs", ".go", ".java", ".qml", ".lua", ".sh", ".toml", ".json",
        ".yaml", ".yml", ".md", ".txt", ".html", ".css", ".sql",
    }
    files = []
    for r, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignore_patterns and not any(ign in d for ign in ignore_patterns)]
        for name in names:
            p = Path(r) / name
            if p.suffix.lower() not in valid_exts or p.name in ignore_patterns:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            files.append((p.relative_to(root), size))
            if len(files) >= limit:
                return files
    return files


def _build_directory_context(target: Path) -> str:
    """Build a compact directory overview: project fingerprint + file tree with sizes."""
    root = find_project_root(target)
    info = fingerprint_project(root)
    ignore_patterns = load_ignore_patterns(root)

    lines = [
        f"# Project: {info['name']}",
        f"Languages: {', '.join(info['languages']) if info['languages'] else 'N/A'}",
        f"Build systems: {', '.join(info['build_systems']) if info['build_systems'] else 'N/A'}",
        f"Code files scanned: {info['total_files']}",
    ]

    files = _walk_code_files(root, ignore_patterns)
    if files:
        lines.append("")
        lines.append("## Files")
        total = 0
        for rel, size in files:
            lines.append(f"- {rel} ({size:,} bytes)")
            total += size
        lines.append("")
        lines.append(f"Total size of {len(files)} listed files: {total:,} bytes")
    return "\n".join(lines)


def collect_summary_input(target: Optional[str], ref: Optional[str]) -> Tuple[str, str, str]:
    """Collect input for summarization. Returns (kind, content, label).

    Priority: piped stdin > explicit file/dir > git diff (staged then unstaged).
    """
    if not sys.stdin.isatty():
        content = sys.stdin.read(MAX_SUMMARY_BYTES)
        if content.strip():
            return ("stdin stream", content, "stdin")

    if target:
        path = Path(target).expanduser().resolve()
        if not path.exists():
            console.print(f"[bold red]Error:[/bold red] Path not found: [yellow]{target}[/yellow]")
            sys.exit(1)
        if path.is_dir():
            return ("directory", _build_directory_context(path), str(path))
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(MAX_SUMMARY_BYTES)
        return ("file", content, str(path))

    diff = get_git_diff(ref)
    if diff:
        return ("git diff", diff[:MAX_SUMMARY_BYTES], f"git diff {ref or '--staged/--unstaged'}")

    return ("", "", "")


def _resolve_provider(local: bool = False, model: Optional[str] = None):
    """Pick the LLM provider: forced local Ollama, or the globally configured one."""
    if local:
        from capture_help.config import settings
        from capture_help.providers.ollama import OllamaProvider

        target_model = model or settings.deepseek_model or "qwen2.5-coder"
        console.print(f"[bold cyan]🦙 Using local Ollama model:[/bold cyan] [bold white]{target_model}[/bold white] "
                      f"(http://localhost:11434)\n")
        return OllamaProvider(model=target_model, base_url=settings.deepseek_base_url)
    return get_provider(model=model)


def summarize_command(
    target: Optional[str] = None,
    ref: Optional[str] = None,
    copy: bool = False,
    export: Optional[str] = None,
    local: bool = False,
    model: Optional[str] = None,
):
    """Summarize git changes, a source file, a directory, or piped stdin."""
    print_header("Content Summarizer", "Condensing code, diffs, and logs into key takeaways")

    kind, content, label = collect_summary_input(target, ref)
    if not content.strip():
        console.print("[bold yellow]Nothing to summarize.[/bold yellow]")
        console.print("Pipe some input in (e.g. [bold]git log --oneline | capture-help summarize[/bold]) or pass a file, directory, or use --ref.")
        return

    render_project_badge()
    console.print(f"[bold cyan]Summarizing {kind}:[/bold cyan] [bold white]{label}[/bold white] "
                  f"({len(content.splitlines())} lines)\n")

    provider = _resolve_provider(local=local, model=model)
    prompt = SUMMARIZE_PROMPT.format(kind=kind, content=content)
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}], temperature=0.3)
    full_text, _ = stream_response(gen, console)

    if copy and full_text:
        copy_to_clipboard(full_text)
    if export and full_text:
        export_to_markdown(export, full_text)
