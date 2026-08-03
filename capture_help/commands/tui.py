import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table

from capture_help.project import find_project_root, fingerprint_project
from capture_help.utils import print_header

console = Console()

def tui_command():
    """Launch interactive Rich Terminal User Interface dashboard."""
    print_header("TUI Dashboard", "v2.0.0 Terminal Control Panel")

    root = find_project_root()
    info = fingerprint_project(root)

    layout = Layout()
    layout.split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=2),
    )

    # Left Panel: File Explorer & Project Info
    file_table = Table(title="📁 Project Files", border_style="cyan", expand=True)
    file_table.add_column("File / Directory", style="bold yellow")
    file_table.add_column("Type", style="dim white")

    for p in list(root.iterdir())[:12]:
        if p.name.startswith("."):
            continue
        ftype = "Dir" if p.is_dir() else "File"
        file_table.add_row(p.name, ftype)

    layout["left"].update(Panel(file_table, border_style="cyan", title="Project Explorer"))

    # Right Panel: Agent Dashboard & Shortcuts
    dash_table = Table(title="⚡ Agent Quick Shortcuts", border_style="green", expand=True)
    dash_table.add_column("Shortcut Command", style="bold yellow")
    dash_table.add_column("Action", style="white")
    dash_table.add_row("capture-help chat", "Start interactive AI pair-programming chat")
    dash_table.add_row("capture-help ask '<q>'", "Search codebase and ask architecture questions")
    dash_table.add_row("capture-help doctor", "Run diagnostic health checks")
    dash_table.add_row("capture-help index", "Index codebase into SQLite RAG database")
    dash_table.add_row("capture-help hook install", "Install Git pre-commit security review hook")
    dash_table.add_row("capture-help plugin list", "List and enable domain rules (QML, FastAPI, CMake)")

    layout["right"].update(Panel(dash_table, border_style="green", title="Control Center"))

    console.print(layout)
    console.print("\n[bold green]✓ capture-help v2.0.0 TUI Operational![/bold green] Type any command above to begin.")
