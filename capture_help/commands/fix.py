import re
from typing import Optional
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import (
    print_header,
    read_stdin_or_file,
    stream_response,
    prompt_apply_patch,
    render_project_badge,
)

console = Console()

FIX_PROMPT = """You are a senior code repair engineer.
Analyze the following code from '{filename}' for bugs, logic errors, memory leaks, security vulnerabilities, or anti-patterns:

```{language}
{content}
```

Instructions:
1. Identify all bugs or anti-patterns with line references or function names.
2. Provide the COMPLETE fixed version of the file inside a single triple-backtick code block (e.g. ```{language}\n...code...\n```).
3. Highlight what was changed and why.

Format your response with headings: '## 🐛 Detected Issues', '## 🛠️ Fixed Implementation', '## 📝 Summary of Fixes'."""

def fix_command(target: Optional[str] = None):
    """Analyze a file or piped input and suggest concrete fixes with interactive diff patching."""
    content, path, name = read_stdin_or_file(target)
    print_header("Code Fixer & Debugger", f"Diagnosing {name}")
    render_project_badge()

    lang = path.suffix.lstrip(".") if path else "text"
    console.print(f"[bold cyan]Analyzing:[bold white] {name} ({len(content.splitlines())} lines)[/bold white]\n")

    provider = get_provider()
    prompt = FIX_PROMPT.format(filename=name, language=lang, content=content[:20_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    full_response, stats = stream_response(gen, console)

    # Extract suggested code block if path exists (file-based)
    if path:
        code_match = re.search(r"```(?:\w+)?\n(.*?)```", full_response, re.DOTALL)
        if code_match:
            new_code = code_match.group(1)
            prompt_apply_patch(path, content, new_code)
