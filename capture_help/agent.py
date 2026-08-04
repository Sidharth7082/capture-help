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

AGENT_SYSTEM_PROMPT = """You are `capture-help`, an autonomous agentic AI coding & Linux terminal assistant powered by DeepSeek API.

CRITICAL MANDATE:
You are equipped with direct terminal execution capabilities. When the user asks ANY question or request that involves checking system info, running commands, downloading packages, building code, or reading/writing files:
1. DO NOT give instructions or tell the user to run commands manually.
2. DO NOT ask "Let me know if you want me to run it for you".
3. YOU MUST IMMEDIATELY EMIT `TOOL_RUN: <command>` ON ITS OWN LINE to execute the command directly!

Available Tool Commands:
- TOOL_RUN: <command to execute in bash>
- TOOL_READ: <filepath to read>
- TOOL_WRITE: <filepath to write>
- TOOL_SEARCH: <query to search codebase>"""

def clean_tool_cmd(cmd: str) -> str:
    """Safely strip outer wrapping quotes or backticks without destroying internal/closing shell quotes."""
    cmd = cmd.strip()
    if (cmd.startswith("`") and cmd.endswith("`")) or \
       (cmd.startswith('"') and cmd.endswith('"') and cmd.count('"') == 2) or \
       (cmd.startswith("'") and cmd.endswith("'") and cmd.count("'") == 2):
        cmd = cmd[1:-1].strip()
    return cmd

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

ARCH_PACKAGE_MAP = {
    "clamscan": "clamav",
    "htop": "htop",
    "btop": "btop",
    "nmap": "nmap",
    "docker": "docker",
    "git": "git",
    "pip": "python-pip",
    "wget": "wget",
    "curl": "curl",
    "ffmpeg": "ffmpeg",
    "tree": "tree",
    "rg": "ripgrep",
    "fd": "fd",
    "jq": "jq",
}


def resolve_missing_command_hint(cmd_str: str, err_out: str) -> str:
    """If command not found, append Arch Linux package installation hint."""
    if "command not found" in err_out or "not found" in err_out.lower():
        cmd_tokens = cmd_str.strip().split()
        missing_cmd = cmd_tokens[0] if cmd_tokens else cmd_str
        pkg = ARCH_PACKAGE_MAP.get(missing_cmd, missing_cmd)
        hint = f"\n\n[ARCH LINUX HINT]: '{missing_cmd}' is not installed. You can install it on Arch Linux using: TOOL_RUN: sudo pacman -S {pkg} --noconfirm"
        return err_out + hint
    return err_out


def agent_run_command(command_str: str) -> str:
    from rich import box
    is_pkg = any(k in command_str for k in ["pacman", "yay", "paru", "pip install", "apt"])
    title_text = "📦 Proposed Package Installation: RUN_COMMAND" if is_pkg else "⚡ Proposed Tool Action: RUN_COMMAND"
    border = "yellow" if is_pkg else "cyan"

    console.print(Panel(
        f"[bold yellow]{command_str}[/bold yellow]",
        title=f"[bold {border}]{title_text}[/bold {border}]",
        border_style=border,
        box=box.ROUNDED,
        expand=False
    ))

    if Confirm.ask("[bold yellow]Execute command?[/bold yellow]", default=True):
        try:
            res = subprocess.run(command_str, shell=True, capture_output=True, text=True, timeout=60)
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            out = ""
            if stdout:
                out += f"{stdout}\n"
            if stderr:
                out += f"[STDERR]:\n{stderr}\n"
            if not out:
                out = "Command executed cleanly with 0 output."

            out_with_hint = resolve_missing_command_hint(command_str, out)

            console.print(Panel(
                out_with_hint[:4000],
                title=f"[bold green]✓ Execution Output ({command_str[:30]})[/bold green]",
                border_style="bright_blue",
                box=box.ROUNDED,
                expand=False
            ))
            return out_with_hint[:10_000]
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 60 seconds."
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

def clean_dsml_response(text: str) -> str:
    """Clean raw DSML or tool XML tags from display response text."""
    text = re.sub(r"<\|\s*\|\s*DSML\s*\|\s*\|\s*tool_calls>.*?</\|\s*\|\s*DSML\s*\|\s*\|\s*tool_calls>", "", text, flags=re.DOTALL)
    text = re.sub(r"<\|\s*\|\s*DSML\s*\|\s*\|.*?>", "", text)
    return text.strip()

def check_and_execute_agent_tools(response_text: str) -> Tuple[bool, str]:
    """Inspect LLM response for embedded tool requests (TOOL_RUN or DeepSeek DSML tool calls) and execute them."""
    tool_executed = False
    output_log = ""

    # 1. Standard TOOL_RUN: command
    run_matches = re.findall(r"TOOL_RUN:\s*([^\n]+)", response_text, re.IGNORECASE)
    for cmd in run_matches:
        cmd = clean_tool_cmd(cmd)
        console.print(f"[bold cyan]🔧 Executing Tool: Run Command '{cmd}'[/bold cyan]")
        res = agent_run_command(cmd)
        output_log += f"\n[Tool Result RUN_COMMAND '{cmd}']:\n{res}\n"
        tool_executed = True

    # 2. DeepSeek DSML tool_calls format
    dsml_matches = re.findall(
        r"parameter[^>]*>(.*?)</\|",
        response_text,
        re.DOTALL | re.IGNORECASE
    )
    for cmd in dsml_matches:
        cmd = clean_tool_cmd(cmd)
        if cmd and not tool_executed:
            console.print(f"[bold cyan]🔧 Executing DeepSeek Tool Call: '{cmd}'[/bold cyan]")
            res = agent_run_command(cmd)
            output_log += f"\n[Tool Result RUN_COMMAND '{cmd}']:\n{res}\n"
            tool_executed = True

    # 3. TOOL_READ: path
    read_matches = re.findall(r"TOOL_READ:\s*([^\n]+)", response_text, re.IGNORECASE)
    for path in read_matches:
        path = clean_tool_cmd(path)
        console.print(f"[bold cyan]🔧 Executing Tool: Read File '{path}'[/bold cyan]")
        res = agent_read_file(path)
        output_log += f"\n[Tool Result READ_FILE '{path}']:\n{res}\n"
        tool_executed = True

    # 4. TOOL_SEARCH: query
    search_matches = re.findall(r"TOOL_SEARCH:\s*([^\n]+)", response_text, re.IGNORECASE)
    for q in search_matches:
        q = clean_tool_cmd(q)
        console.print(f"[bold cyan]🔧 Executing Tool: Search Code '{q}'[/bold cyan]")
        res = agent_search_codebase(q)
        output_log += f"\n[Tool Result SEARCH_CODE '{q}']:\n{res}\n"
        tool_executed = True

    # 5. TOOL_WRITE: path
    write_matches = re.findall(r"TOOL_WRITE:\s*([^\n]+)", response_text, re.IGNORECASE)
    for path in write_matches:
        path = clean_tool_cmd(path)
        console.print(f"[bold cyan]🔧 Executing Tool: Write File '{path}'[/bold cyan]")
        code_block = re.search(r"```(?:\w+)?\n(.*?)```", response_text, re.DOTALL)
        content = code_block.group(1) if code_block else ""
        res = agent_write_file(path, content)
        output_log += f"\n[Tool Result WRITE_FILE '{path}']:\n{res}\n"
        tool_executed = True

    return tool_executed, output_log
