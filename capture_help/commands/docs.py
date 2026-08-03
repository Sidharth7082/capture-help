from typing import Optional
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import (
    print_header,
    read_stdin_or_file,
    stream_response,
    render_project_badge,
    copy_to_clipboard,
    export_to_markdown,
)

console = Console()

DOCS_PROMPT = """You are a technical documentation specialist.
Generate comprehensive documentation for source code '{filename}':

```{language}
{content}
```

Instructions:
1. Provide a High-Level Overview of the file's purpose and role in the system.
2. List API Interfaces / Public Classes / Functions with signatures, parameter descriptions, return types, and usage examples.
3. Provide the complete code file updated with clean, professional docstrings / comments (Doxygen / JSDoc / Google Python style depending on language).

Format with Markdown headings: '## 📚 Architecture Overview', '## 🔌 API Reference', '## 📝 Documented Code'."""

def docs_command(
    target: Optional[str] = None,
    copy: bool = False,
    export: Optional[str] = None,
):
    """Generate technical documentation and docstrings for a source file or piped stdin."""
    content, path, name = read_stdin_or_file(target)
    print_header("Documentation Generator", f"Documenting {name}")
    render_project_badge()

    lang = path.suffix.lstrip(".") if path else "text"
    console.print(f"[bold cyan]Generating docs for:[bold white] {name}[/bold white]\n")

    provider = get_provider()
    prompt = DOCS_PROMPT.format(filename=name, language=lang, content=content[:20_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    full_output, stats = stream_response(gen, console)

    if copy and full_output:
        copy_to_clipboard(full_output)
    if export and full_output:
        export_to_markdown(export, full_output)
