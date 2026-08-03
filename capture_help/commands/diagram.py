from typing import Optional
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, read_stdin_or_file, stream_response, copy_to_clipboard, export_to_markdown

console = Console()

DIAGRAM_PROMPT = """You are a software architecture visualizer.
Generate a Mermaid.js diagram (class diagram or flowchart) for the following code '{filename}':

```{language}
{content}
```

Instructions: Output valid ```mermaid code blocks with node labels quoted properly."""

def diagram_command(
    target: Optional[str] = None,
    copy: bool = False,
    export: Optional[str] = None,
):
    """Generate Mermaid architecture diagram for code file or piped stdin."""
    content, path, name = read_stdin_or_file(target)
    print_header("Mermaid Diagram Generator", f"Visualizing {name}")

    lang = path.suffix.lstrip(".") if path else "text"
    console.print(f"[bold cyan]Generating Mermaid diagram for:[bold white] {name}[/bold white]\n")

    provider = get_provider()
    prompt = DIAGRAM_PROMPT.format(filename=name, language=lang, content=content[:15_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    full_output, stats = stream_response(gen, console)

    if copy and full_output:
        copy_to_clipboard(full_output)
    if export and full_output:
        export_to_markdown(export, full_output)
