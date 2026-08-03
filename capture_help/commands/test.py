from typing import Optional
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, read_stdin_or_file, stream_response, render_project_badge

console = Console()

TEST_PROMPT = """You are a Principal QA and Test Automation Engineer.
Generate a complete, production-ready unit test suite for '{filename}':

```{language}
{content}
```

Instructions:
1. Select the standard test framework for this language (e.g. pytest/unittest for Python, Catch2/GTest for C++, Jest/Vitest for JS/TS, cargo test for Rust).
2. Cover happy paths, edge cases, null/empty inputs, and boundary conditions.
3. Provide runnable, ready-to-use test file code block."""

def test_command(target: Optional[str] = None):
    """Generate unit tests for a source file or piped stdin."""
    content, path, name = read_stdin_or_file(target)
    print_header("Unit Test Generator", f"Generating test suite for {name}")
    render_project_badge()

    lang = path.suffix.lstrip(".") if path else "text"
    console.print(f"[bold cyan]Analyzing target:[bold white] {name}[/bold white]\n")

    provider = get_provider()
    prompt = TEST_PROMPT.format(filename=name, language=lang, content=content[:20_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
