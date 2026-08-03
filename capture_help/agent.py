import os
import sys
import re
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

AGENT_SYSTEM_PROMPT = """You are Antigravity, a powerful agentic AI coding assistant powered by DeepSeek.
You are pair programming with a USER to solve their coding tasks, build software, debug errors, and optimize projects.

You have access to the user's workspace and system tools:
1. READ_FILE: read file content (e.g. `TOOL_READ: path/to/file`)
2. WRITE_FILE: create or update file content (e.g. `TOOL_WRITE: path/to/file\n```language\ncontent\n````)
3. RUN_COMMAND: execute terminal commands (e.g. `TOOL_RUN: git status`)
4. SEARCH_CODE: search project for symbols or text (e.g. `TOOL_SEARCH: query`)

Guidelines:
- Keep your responses concise, clear, and action-oriented.
- Format responses in GitHub-style Markdown with syntax highlighting.
- When proposing file edits or shell commands, format them clearly.
- Maintain professional, pair-programming style."""

def agent_read_file(filepath: str) -> str:
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
    path = Path(filepath).expanduser().resolve()

    console.print(f"\n[bold cyan]📝 Proposed Tool Action: WRITE_FILE[/bold cyan] [bold white]{path}[/bold white]")
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
    console.print(f"\n[bold cyan]⚡ Proposed Tool Action: RUN_COMMAND[/bold cyan] [bold yellow]{command_str}[/bold yellow]")

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
    matches, scanned_count = search_project_context(query, top_k=4)
    if not matches:
        return f"No code matches found for '{query}' across {scanned_count} scanned files."

    result = f"Found {len(matches)} match(es) across {scanned_count} scanned files:\n"
    for file_path, text, score in matches:
        result += f"\nFile: {file_path.name} (Score: {score:.2f})\nSnippet:\n{text[:1500]}\n"
    return result

def check_and_execute_agent_tools(response_text: str) -> Tuple[bool, str]:
    """Inspect LLM response for embedded tool requests and execute them."""
    tool_executed = False
    output_log = ""

    # 1. TOOL_READ: path
    read_matches = re.findall(r"TOOL_READ:\s*([^\n]+)", response_text)
    for path in read_matches:
        path = path.strip()
        console.print(f"[bold cyan]🔧 Executing Tool: Read File '{path}'[/bold cyan]")
        res = agent_read_file(path)
        output_log += f"\n[Tool Result READ_FILE '{path}']:\n{res}\n"
        tool_executed = True

    # 2. TOOL_RUN: command
    run_matches = re.findall(r"TOOL_RUN:\s*([^\n]+)", response_text)
    for cmd in run_matches:
        cmd = cmd.strip()
        console.print(f"[bold cyan]🔧 Executing Tool: Run Command '{cmd}'[/bold cyan]")
        res = agent_run_command(cmd)
        output_log += f"\n[Tool Result RUN_COMMAND '{cmd}']:\n{res}\n"
        tool_executed = True

    # 3. TOOL_SEARCH: query
    search_matches = re.findall(r"TOOL_SEARCH:\s*([^\n]+)", response_text)
    for q in search_matches:
        q = q.strip()
        console.print(f"[bold cyan]🔧 Executing Tool: Search Code '{q}'[/bold cyan]")
        res = agent_search_codebase(q)
        output_log += f"\n[Tool Result SEARCH_CODE '{q}']:\n{res}\n"
        tool_executed = True

    return tool_executed, output_log
