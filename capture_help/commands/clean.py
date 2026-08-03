from typing import Optional
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, read_stdin_or_file, stream_response

console = Console()

CLEAN_PROMPT = """You are a Code Quality Inspector.
Scan the following code from '{filename}' for dead code, unused imports, orphan variables, or redundant logic:

```{language}
{content}
```

Format with: '## 🧹 Unused Imports & Dead Code', '## ✂️ Refactored Clean Version'."""

def clean_command(filepath: Optional[str] = None):
    """Scan file for dead code, unused imports, and redundant logic."""
    content, path, name = read_stdin_or_file(filepath)
    print_header("Dead Code & Import Cleaner", f"Cleaning {name}")

    lang = path.suffix.lstrip(".") if path else "text"
    console.print(f"[bold cyan]Scanning for dead code in:[bold white] {name}[/bold white]\n")

    provider = get_provider()
    prompt = CLEAN_PROMPT.format(filename=name, language=lang, content=content[:15_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
