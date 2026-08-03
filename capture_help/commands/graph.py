import typer
import re
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

def graph_command():
    """Generate Mermaid.js dependency graph of codebase imports."""
    console.print("[bold cyan]📊 Generating Codebase Dependency Graph...[/bold cyan]\n")
    
    root = Path.cwd()
    py_files = list(root.glob("**/*.py"))
    
    edges = set()
    for p in py_files:
        if "venv" in str(p) or ".git" in str(p):
            continue
        mod_name = p.stem
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                if line.startswith("import ") or line.startswith("from "):
                    match = re.search(r'(?:import|from)\s+([a-zA-Z0-9_\.]+)', line)
                    if match:
                        imp = match.group(1).split(".")[0]
                        if imp not in ["os", "sys", "re", "pathlib", "typing", "json", "time", "subprocess"]:
                            edges.add((mod_name, imp))
        except Exception:
            pass

    mermaid_lines = ["graph TD"]
    for src, dst in sorted(list(edges))[:25]:
        mermaid_lines.append(f"    {src} --> {dst}")

    mermaid_code = "\n".join(mermaid_lines)
    console.print(Panel(mermaid_code, title="🧠 Mermaid.js Dependency Graph", border_style="cyan"))
