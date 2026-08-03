from typing import Optional
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, read_stdin_or_file, stream_response, copy_to_clipboard, export_to_markdown

console = Console()

TRANSLATE_PROMPT = """You are a senior polyglot software engineer.
Translate the following source code from '{filename}' into '{target_language}':

```{src_language}
{content}
```

Instructions:
1. Provide the complete translated code inside a single ```{target_language} code block.
2. Maintain idiomatic patterns, error handling, and performance standards of '{target_language}'.
3. Add a short summary of translation notes."""

def translate_command(
    filepath: str,
    to: str = "cpp",
    copy: bool = False,
    export: Optional[str] = None,
):
    """Translate source code from one programming language to another."""
    content, path, name = read_stdin_or_file(filepath)
    print_header("Code Translator", f"Translating {name} -> {to}")

    src_lang = path.suffix.lstrip(".") if path else "text"
    console.print(f"[bold cyan]Translating:[bold white] {name} ({src_lang}) -> {to}[/bold white]\n")

    provider = get_provider()
    prompt = TRANSLATE_PROMPT.format(filename=name, src_language=src_lang, target_language=to, content=content[:15_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    full_output, stats = stream_response(gen, console)

    if copy and full_output:
        copy_to_clipboard(full_output)
    if export and full_output:
        export_to_markdown(export, full_output)
