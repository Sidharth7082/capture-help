import os
import sqlite3
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from capture_help.project import find_project_root, load_ignore_patterns
from capture_help.utils import print_header

console = Console()

def index_command():
    """Index repository files into local SQLite search database (.capture-help/index.sqlite)."""
    print_header("Codebase Indexer")
    root = find_project_root()
    
    cache_dir = root / ".capture-help"
    cache_dir.mkdir(parents=True, exist_ok=True)
    db_path = cache_dir / "index.sqlite"

    console.print(f"[bold cyan]🔍 Scanning and indexing codebase at:[/bold cyan] [bold white]{root.name}[/bold white]...\n")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS code_index (
            path TEXT PRIMARY KEY,
            filename TEXT,
            content TEXT,
            mtime REAL
        )
    """)

    ignore_patterns = load_ignore_patterns(root)
    valid_exts = {".cpp", ".hpp", ".c", ".h", ".py", ".js", ".ts", ".rs", ".go", ".qml", ".lua", ".sh", ".toml", ".json", ".txt", ".md"}

    indexed_count = 0
    total_bytes = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(description="Indexing project files...", total=None)

        for r, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in ignore_patterns and not any(ign in d for ign in ignore_patterns)]
            for f in files:
                p = Path(r) / f
                if p.suffix.lower() not in valid_exts:
                    continue

                try:
                    mtime = p.stat().st_mtime
                    rel_path = str(p.relative_to(root))

                    # Check if modified
                    cur.execute("SELECT mtime FROM code_index WHERE path = ?", (rel_path,))
                    row = cur.fetchone()
                    if row and row[0] == mtime:
                        indexed_count += 1
                        continue

                    with open(p, "r", encoding="utf-8", errors="ignore") as fo:
                        text = fo.read(100_000)

                    cur.execute(
                        "INSERT OR REPLACE INTO code_index (path, filename, content, mtime) VALUES (?, ?, ?, ?)",
                        (rel_path, p.name, text, mtime)
                    )
                    indexed_count += 1
                    total_bytes += len(text.encode("utf-8"))
                    progress.update(task, description=f"Indexed: [bold yellow]{rel_path}[/bold yellow]")
                except Exception:
                    pass

    conn.commit()
    conn.close()

    console.print(Panel(
        f"[bold green]✓ Codebase Indexing Complete![/bold green]\n"
        f"Indexed Files: [bold white]{indexed_count}[/bold white]\n"
        f"Payload Indexed: [bold white]{total_bytes / 1024:.1f} KB[/bold white]\n"
        f"Database: [dim]{db_path}[/dim]",
        border_style="green",
        expand=False
    ))
