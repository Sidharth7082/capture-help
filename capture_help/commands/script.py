from rich.console import Console

from capture_help.deepseek import get_provider
from capture_help.utils import print_header, stream_response

console = Console()

SCRIPT_PROMPT = """You are a Linux Systems Automation Engineer.
Write a production-ready Bash script for the following task:
'{task}'

Guidelines:
- Include `set -euo pipefail`.
- Include colorful output helpers and dry-run flag support (`--dry-run`).
- Wrap complete code inside a single ```bash code block."""

def script_command(task: str):
    """Generate production-ready Bash automation script."""
    print_header("Bash Script Generator", task)
    console.print(f"[bold cyan]Generating shell script for task:[bold white] '{task}'[/bold white]\n")

    provider = get_provider()
    prompt = SCRIPT_PROMPT.format(task=task)
    gen = provider.stream_completion(messages=[{"role": "user", "content": prompt}])
    stream_response(gen, console)
