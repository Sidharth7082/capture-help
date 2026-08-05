"""`capture-help tui` — a glass dashboard built on Textual.

Falls back to the classic Rich tables when stdout is not a terminal so it can
still be piped safely.
"""

import sys
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Static

from capture_help.project import find_project_root, fingerprint_project
from capture_help.utils import print_header

console = Console()

_ACCENT = "#63c6e2"
_SURFACE = "#12161f"
_EDGE = "#232b3c"
_TEXT = "#e8edf4"
_MUTED = "#8f9aa9"
_SUCCESS = "#4ed98c"
_WARNING = "#e5b95c"

SHORTCUTS = [
    ("capture-help chat", "Start the interactive AI assistant"),
    ("capture-help ask '<q>'", "Query the codebase with citations"),
    ("capture-help doctor", "Run diagnostic health checks"),
    ("capture-help index", "Index the codebase into SQLite"),
    ("capture-help hook install", "Install the Git pre-commit review hook"),
    ("capture-help plugin list", "List and enable domain rules"),
    ("capture-help neofetch", "System & AI compute dashboard"),
]


class TuiDashboardApp(App[None]):
    """Glass control-center dashboard for capture-help."""

    TITLE = "Capture Help"
    SUB_TITLE = "TUI Dashboard"

    BINDINGS = [("q", "quit", "Quit"), ("escape", "quit", "Quit")]

    def __init__(self, project: dict, files: list, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self.files = files

    def compose(self) -> ComposeResult:
        langs = " • ".join(self.project.get("languages", []) or []) or "Generic"
        git_clean = self.project.get("git_clean", True)
        git_text = "✓ Clean" if git_clean else "✗ Modified"
        git_color = _SUCCESS if git_clean else _WARNING

        with Vertical(id="tui-root"):
            yield Label("⚡ Capture Help   TUI Dashboard", id="tui-title")
            yield Label(
                f"▤ Project: {self.project.get('name', 'project')}   "
                f"λ {langs}   ⎇ [{git_color}]{git_text}[/{git_color}]",
                id="tui-subtitle",
            )
            with Horizontal(id="tui-body"):
                with Vertical(classes="tui-card"):
                    yield Label("▤ PROJECT FILES", classes="tui-card-title")
                    body = "\n".join(f"▸ {name}  [dim]{ftype}[/dim]" for name, ftype in self.files)
                    yield Static(body or "—", classes="tui-card-body")
                with Vertical(classes="tui-card"):
                    yield Label("⚡ QUICK COMMANDS", classes="tui-card-title")
                    body = "\n".join(f"[{_ACCENT}]{cmd:<26}[/{_ACCENT}] {desc}" for cmd, desc in SHORTCUTS)
                    yield Static(body, classes="tui-card-body")
            yield Label("q / Esc to quit", id="tui-footer")

    def action_quit(self) -> None:
        self.exit()

    CSS = f"""
    #tui-root {{
        background: #0d1017;
    }}
    #tui-title {{
        color: {_TEXT};
        text-style: bold;
        padding: 1 2 0 2;
    }}
    #tui-subtitle {{
        color: {_MUTED};
        padding: 0 2 1 2;
    }}
    #tui-body {{
        height: 1fr;
        padding: 0 2 1 2;
    }}
    .tui-card {{
        width: 1fr;
        height: 1fr;
        margin: 0 1 0 0;
        background: {_SURFACE};
        border: round {_EDGE};
        border-radius: 12;
        padding: 1 2 1 2;
    }}
    .tui-card-title {{
        color: {_ACCENT};
        text-style: bold;
        margin: 0 0 1 0;
    }}
    .tui-card-body {{
        color: {_TEXT};
    }}
    #tui-footer {{
        color: #5d6878;
        padding: 0 2 1 2;
    }}
    """


def tui_command():
    """Launch interactive Rich Terminal User Interface dashboard."""
    root = find_project_root()
    info = fingerprint_project(root)

    if sys.stdin.isatty() and sys.stdout.isatty():
        files = []
        for p in list(root.iterdir())[:14]:
            if p.name.startswith("."):
                continue
            files.append((p.name, "Dir" if p.is_dir() else "File"))
        TuiDashboardApp(project=info, files=files).run()
        return

    # Non-interactive fallback: classic Rich tables.
    print_header("TUI Dashboard", "v2.0.0 Terminal Control Panel")
    file_table = Table(title="▤ Project Files", border_style=_EDGE, box=box.ROUNDED, expand=True)
    file_table.add_column("File / Directory", style="bold " + _TEXT)
    file_table.add_column("Type", style="dim " + _MUTED)
    for p in list(root.iterdir())[:12]:
        if p.name.startswith("."):
            continue
        file_table.add_row(p.name, "Dir" if p.is_dir() else "File")
    dash_table = Table(title="⚡ Quick Commands", border_style=_EDGE, box=box.ROUNDED, expand=True)
    dash_table.add_column("Shortcut Command", style="bold " + _TEXT)
    dash_table.add_column("Action", style=_MUTED)
    for cmd, desc in SHORTCUTS:
        dash_table.add_row(cmd, desc)
    console.print(file_table)
    console.print(dash_table)
    console.print(f"\n[{_SUCCESS}]✓ capture-help TUI operational![/{_SUCCESS}]")
