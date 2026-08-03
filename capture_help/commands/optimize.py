from typing import Optional
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, read_stdin_or_file, stream_response, render_project_badge

console = Console()

OPTIMIZE_PROMPT = """You are a High Performance Computing & System Optimization Engineer.
Analyze '{filename}' for performance bottlenecks, unnecessary memory allocations, redundant loops, and slow operations:

```{language}
{content}
```

Instructions:
1. Provide a Time Complexity (Big-O) & Memory Complexity analysis of key functions.
2. Identify bottlenecks (e.g. O(N^2) loops, redundant memory copies, unindexed queries, un-cached allocations).
3. Provide the optimized code with benchmark/efficiency expectations.

Format with Markdown headings: '## ⚡ Complexity & Bottleneck Analysis', '## 🚀 Optimized Implementation', '## 📊 Expected Performance Gains'."""

def optimize_command(target: Optional[str] = None):
    """Analyze a file or piped stdin and suggest performance & memory optimizations."""
    content, path, name = read_stdin_or_file(target)
    print_header("Performance Optimizer", f"Optimizing {name}")
    render_project_badge()

    lang = path.suffix.lstrip(".") if path else "text"
    console.print(f"[bold cyan]Analyzing performance of:[bold white] {name}[/bold white]\n")

    provider = get_provider()
    prompt = OPTIMIZE_PROMPT.format(filename=name, language=lang, content=content[:20_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
