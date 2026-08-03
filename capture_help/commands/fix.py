from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, read_file_content, stream_response

console = Console()

FIX_PROMPT = """You are a senior code repair engineer.
Analyze the following code from '{filename}' for bugs, logic errors, memory leaks, security vulnerabilities, or anti-patterns:

```{language}
{content}
```

Instructions:
1. Identify all bugs or anti-patterns with line references or function names.
2. Provide a clear, clean refactored version of the code that fixes all identified issues.
3. Highlight what was changed and why.

Format your response with clear Markdown headings: '## 🐛 Detected Issues', '## 🛠️ Refactored Code', '## 📝 Summary of Fixes'."""

def fix_command(filepath: str):
    """Analyze a file and suggest concrete fixes for bugs and code smells."""
    content, path = read_file_content(filepath)
    print_header("Code Fixer & Debugger", f"Diagnosing {path.name}")

    lang = path.suffix.lstrip(".") or "text"
    console.print(f"[bold cyan]Analyzing file:[bold white] {path.name} ({len(content.splitlines())} lines)[/bold white]\n")

    provider = get_provider()
    prompt = FIX_PROMPT.format(filename=path.name, language=lang, content=content[:20_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
