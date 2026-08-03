import typer
import re
from pathlib import Path
from rich.console import Console

console = Console()

def redact_command(
    text_or_file: str = typer.Argument(..., help="Text prompt or file path to redact secrets from")
):
    """Scan and redact API keys, passwords, and IP addresses before sending prompts."""
    content = text_or_file
    p = Path(text_or_file)
    if p.exists() and p.is_file():
        content = p.read_text(encoding="utf-8")
        
    # Redact patterns
    redacted = content
    redacted = re.sub(r'sk-[a-zA-Z0-9]{32,}', '[REDACTED_API_KEY]', redacted)
    redacted = re.sub(r'ghp_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]', redacted)
    redacted = re.sub(r'(\d{1,3}\.){3}\d{1,3}', '[REDACTED_IP_ADDRESS]', redacted)
    redacted = re.sub(r'(?i)(password|secret|key)\s*[:=]\s*["\']?[^\s"\'\n]+', r'\1: [REDACTED]', redacted)

    console.print("[bold green]🔒 Redacted Output Sanitized for Privacy:[/bold green]\n")
    console.print(redacted)
