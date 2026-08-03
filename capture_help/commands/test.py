from pathlib import Path
from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, read_file_content, stream_response

console = Console()

TEST_PROMPT = """You are a Principal QA and Test Automation Engineer.
Generate a complete, production-ready unit test suite for '{filename}':

```{language}
{content}
```

Instructions:
1. Select the standard test framework for this language (e.g. pytest/unittest for Python, Catch2/GTest for C++, Jest/Vitest for JS/TS, cargo test for Rust).
2. Cover:
   - Happy paths & core business logic
   - Edge cases, null/empty inputs, boundary conditions
   - Error handling & exception assertions
3. Provide runnable, ready-to-use test file code block."""

def test_command(filepath: str):
    """Generate unit tests for a source file."""
    content, path = read_file_content(filepath)
    print_header("Unit Test Generator", f"Generating test suite for {path.name}")

    lang = path.suffix.lstrip(".") or "text"
    console.print(f"[bold cyan]Analyzing target file:[bold white] {path.name}[/bold white]\n")

    provider = get_provider()
    prompt = TEST_PROMPT.format(filename=path.name, language=lang, content=content[:20_000])
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
