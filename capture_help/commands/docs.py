from pathlib import Path
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, read_file_content, stream_response

console = Console()

DOCS_PROMPT = """You are a technical documentation specialist.
Generate comprehensive documentation for the source file '{filename}':

```{language}
{content}
```

Instructions:
1. Provide a High-Level Overview of the file's purpose and role in the system.
2. List API Interfaces / Public Classes / Functions with signatures, parameter descriptions, return types, and usage examples.
3. Provide the complete code file updated with clean, professional docstrings / comments (Doxygen / JSDoc / Google Python style depending on language).

Format with Markdown headings: '## 📚 Architecture Overview', '## 🔌 API Reference', '## 📝 Documented Code'."""

def docs_command(filepath: str):
    """Generate technical documentation and docstrings for a source file."""
    content, path = read_file_content(filepath)
    print_header("Documentation Generator", f"Documenting {path.name}")

    lang = path.suffix.lstrip(".") or "text"
    console.print(f"[bold cyan]Generating docs for:[bold white] {path.name}[/bold white]\n")

    provider = get_provider()
    prompt = DOCS_PROMPT.format(filename=path.name, language=lang, content=content[:20_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
