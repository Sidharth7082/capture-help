import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm

from capture_help.project import search_project_context
from capture_help.utils import get_git_diff

console = Console()

def agent_read_file(filepath: str) -> str:
    """Read contents of a file for the AI agent."""
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        return f"Error: File '{filepath}' does not exist."
    if path.is_dir():
        return f"Error: '{filepath}' is a directory."

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50_000)
        return f"--- Content of {path.name} ({len(content.splitlines())} lines) ---\n{content}"
    except Exception as e:
        return f"Error reading '{filepath}': {str(e)}"

def agent_write_file(filepath: str, content: str) -> str:
    """Write or update a file with AI generated code."""
    path = Path(filepath).expanduser().resolve()

    console.print(f"\n[bold cyan]📝 Proposed Write to:[/bold cyan] [bold white]{path}[/bold white]")
    console.print(Syntax(content[:1500] + ("..." if len(content) > 1500 else ""), "python", theme="monokai"))

    if Confirm.ask(f"[bold yellow]Allow writing to {path.name}?[/bold yellow]", default=True):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Success: File '{path.name}' written successfully."
        except Exception as e:
            return f"Error writing file: {str(e)}"
    return "Action cancelled by user."

def agent_run_command(command_str: str) -> str:
    """Execute a terminal shell command with user confirmation."""
    console.print(f"\n[bold cyan]⚡ Proposed Terminal Command:[/bold cyan] [bold yellow]{command_str}[/bold yellow]")

    if Confirm.ask("[bold yellow]Execute command?[/bold yellow]", default=True):
        try:
            res = subprocess.run(command_str, shell=True, capture_output=True, text=True, timeout=30)
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            out = ""
            if stdout:
                out += f"STDOUT:\n{stdout}\n"
            if stderr:
                out += f"STDERR:\n{stderr}\n"
            if not out:
                out = "Command executed cleanly with 0 output."
            return out[:10_000]
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 30 seconds."
        except Exception as e:
            return f"Error executing command: {str(e)}"
    return "Command execution cancelled by user."

def agent_search_codebase(query: str) -> str:
    """Search codebase for matches."""
    matches, scanned_count = search_project_context(query, top_k=4)
    if not matches:
        return f"No code matches found for '{query}' across {scanned_count} scanned files."

    result = f"Found {len(matches)} match(es) across {scanned_count} scanned files:\n"
    for file_path, text, score in matches:
        result += f"\nFile: {file_path.name} (Score: {score:.2f})\nSnippet:\n{text[:1500]}\n"
    return result
