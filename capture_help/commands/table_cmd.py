import typer
import json
import csv
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

def table_command(
    file_or_text: str = typer.Argument(..., help="Path to CSV/JSON file or raw text to render as a beautiful table")
):
    """Format CSV or JSON data into a stunning rounded Rich terminal table."""
    p = Path(file_or_text)
    content = file_or_text
    if p.exists() and p.is_file():
        content = p.read_text(encoding="utf-8", errors="ignore")

    table = Table(box=box.ROUNDED, border_style="cyan")

    # 1. Try JSON parsing
    try:
        data = json.loads(content)
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            headers = list(data[0].keys())
            for h in headers:
                table.add_column(str(h), style="bold yellow")
            for row in data:
                table.add_row(*[str(row.get(h, "")) for h in headers])
            console.print(table)
            return
    except Exception:
        pass

    # 2. Try CSV parsing
    try:
        lines = content.strip().splitlines()
        reader = csv.reader(lines)
        rows = list(reader)
        if rows:
            headers = rows[0]
            for h in headers:
                table.add_column(str(h), style="bold yellow")
            for r in rows[1:]:
                table.add_row(*[str(cell) for cell in r])
            console.print(table)
            return
    except Exception:
        pass

    console.print("[yellow]Could not parse input as valid CSV or JSON.[/yellow]")
