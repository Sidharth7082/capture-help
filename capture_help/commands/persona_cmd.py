"""CLI command for managing capture-help character personas."""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from capture_help import persona as persona_mod
from capture_help.utils import print_header

console = Console()

BUILTIN_TEMPLATES = {
    "aggressive": {
        "display_name": "Aggressive Mode",
        "description": "Brutal efficiency: zero fluff, direct code focus, action-ready answers.",
        "greeting": "Cut the preamble. What do you need?",
        "tags": ["productivity", "no-fluff"],
        "system_prompt": (
            "You are capture-help in 'aggressive' mode: brutally efficient, zero fluff, "
            "maximum directness.\n\n"
            "- Give terse, action-ready answers. No pleasantries, no hedging, no filler.\n"
            "- Lead with the answer or the code; explain only when asked.\n"
            "- Use sharp, confident language. Point out flaws plainly.\n"
            "- When the task involves the terminal, act: emit TOOL_RUN commands directly.\n"
            "- Do not soften criticism or pad responses with caveats."
        ),
    },
    "senior": {
        "display_name": "Senior Architect",
        "description": "Senior architect perspective: design patterns, edge cases, scalability.",
        "greeting": "Show me the design. I'll tell you where it breaks.",
        "tags": ["architecture", "senior"],
        "system_prompt": (
            "You are a senior software architect reviewing and guiding production systems.\n\n"
            "- Lead with design considerations: scalability, maintainability, edge cases, and failure modes.\n"
            "- Identify trade-offs and recommend pragmatic decisions with clear rationale.\n"
            "- Provide production-grade code with error handling and tests in mind.\n"
            "- Ask clarifying questions only when they materially change the design."
        ),
    },
}


def persona_list_command():
    """List all installed personas and mark the active one."""
    print_header("Character Personas", f"{persona_mod.PERSONAS_DIR}")

    active = persona_mod.get_active_persona()
    active_name = active.name if active else None
    personas = persona_mod.list_personas()

    table = Table(title="🎭 Installed Personas", border_style="cyan")
    table.add_column("Name", style="bold yellow")
    table.add_column("Display Name", style="bold white")
    table.add_column("Active", style="bold green")
    table.add_column("Description", style="dim white")

    if active is None:
        table.add_row("(default)", "Standard AI Assistant", "✓", "Default terminal coding assistant.")
    for p in personas:
        table.add_row(p.name, p.display_name, "✓" if p.name == active_name else "", p.description)

    console.print(table)
    console.print("\n[dim]Use [bold white]capture-help persona create <name>[/bold white] to add your own "
                  "[bold white]persona activate <name>[/bold white] to switch.[/dim]")


def persona_show_command(name: str):
    """Show the full definition (including system prompt) of a persona."""
    try:
        p = persona_mod.get_persona(name)
    except persona_mod.PersonaError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(1)

    print_header(f"Persona: {p.display_name}")
    console.print(f"[bold yellow]Name:[/bold yellow] {p.name}")
    console.print(f"[bold yellow]Display:[/bold yellow] {p.display_name}")
    console.print(f"[bold yellow]Description:[/bold yellow] {p.description}")
    console.print(f"[bold yellow]Greeting:[/bold yellow] {p.greeting}")
    if p.tags:
        console.print(f"[bold yellow]Tags:[/bold yellow] {', '.join(p.tags)}")
    console.print("\n[bold yellow]System Prompt:[/bold yellow]\n")
    console.print(p.system_prompt)


def persona_templates_command():
    """List built-in persona templates you can start from."""
    print_header("Built-in Persona Templates")
    for name, data in BUILTIN_TEMPLATES.items():
        console.print(f"[bold cyan]{name}[/bold cyan] — [bold white]{data['display_name']}[/bold white]")
        console.print(f"  {data['description']}\n")


def persona_create_command(
    name: str,
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Start from a built-in template (see 'persona templates')."),
):
    """Create a new persona. Persona behavior is fully under your control.

    The system prompt is not restricted by capture-help: write whatever
    behavior, tone, and rules you want the persona to follow.
    """
    if not name or not name.replace("_", "").isalnum():
        console.print("[bold red]Error:[/bold red] Persona name must be alphanumeric (underscores allowed).")
        raise typer.Exit(1)

    dest = persona_mod.PERSONAS_DIR / f"{name}.json"
    if dest.exists():
        console.print(f"[bold red]Error:[/bold red] Persona '{name}' already exists. Delete it first to recreate.")
        raise typer.Exit(1)

    if template:
        data = BUILTIN_TEMPLATES.get(template.lower())
        if not data:
            console.print(f"[bold red]Error:[/bold red] Unknown template '{template}'. Run 'persona templates' for options.")
            raise typer.Exit(1)
        system_prompt = data["system_prompt"]
        display_name = data["display_name"]
        description = data["description"]
        greeting = data["greeting"]
        tags = data["tags"]
        console.print(f"[bold cyan]Starting from template '{template}'.[/bold cyan] "
                      "You can edit the prompt with 'persona edit' afterwards.\n")
    else:
        system_prompt = _read_multiline("System prompt (multi-line; press Ctrl+D on an empty line to finish):")
        display_name = typer.prompt("Display name", default=name)
        description = typer.prompt("Short description", default="")
        greeting = typer.prompt("Greeting line", default="")
        tags_raw = typer.prompt("Comma-separated tags", default="")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    if not system_prompt.strip():
        console.print("[bold red]Error:[/bold red] System prompt cannot be empty.")
        raise typer.Exit(1)

    persona_mod._ensure_dirs()
    dest.write_text(json.dumps({
        "name": name,
        "display_name": display_name,
        "description": description,
        "greeting": greeting,
        "tags": tags,
        "system_prompt": system_prompt.strip(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    console.print(f"[bold green]✓ Persona '{name}' created![/bold green] Activate it with "
                  f"[bold white]capture-help persona activate {name}[/bold white].")


def persona_edit_command(name: str):
    """Open the persona JSON in your $EDITOR (falls back to interactive prompt)."""
    path = persona_mod.PERSONAS_DIR / f"{name}.json"
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] No persona named '{name}'.")
        raise typer.Exit(1)

    import os
    import subprocess
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", ""))
    if editor:
        try:
            subprocess.run(f"{editor} {path}", shell=True, check=True)
            console.print(f"[bold green]✓ Edited '{name}'. Validate with 'persona show {name}'.[/bold green]")
            return
        except Exception:
            pass
    console.print(f"[bold yellow]No $EDITOR set. Editing interactively...[/bold yellow]")
    p = persona_mod.get_persona(name)
    new_prompt = _read_multiline(f"System prompt for '{name}' (current prompt shown above; Ctrl+D to finish):")
    if new_prompt.strip():
        data = json.loads(path.read_text(encoding="utf-8"))
        data["system_prompt"] = new_prompt.strip()
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"[bold green]✓ Updated system prompt for '{name}'.[/bold green]")


def persona_activate_command(name: str):
    """Activate a persona so it applies to all chat sessions."""
    try:
        p = persona_mod.activate_persona(name)
    except persona_mod.PersonaError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(1)
    console.print(f"[bold green]{persona_mod.render_banner(p)}[/bold green]")


def persona_reset_command():
    """Reset back to the default capture-help assistant."""
    persona_mod.reset_persona()
    console.print("[bold green]✓ Persona reset to default AI Assistant.[/bold green]")


def persona_delete_command(name: str):
    """Permanently delete a persona file."""
    path = persona_mod.PERSONAS_DIR / f"{name}.json"
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] No persona named '{name}'.")
        raise typer.Exit(1)
    active = persona_mod.get_active_persona()
    path.unlink()
    if active and active.name == name:
        persona_mod.reset_persona()
    console.print(f"[bold green]✓ Persona '{name}' deleted.[/bold green]")


def persona_export_command(name: str, out: Optional[str] = None):
    """Export a persona to a JSON file (default: <name>.persona.json)."""
    path = persona_mod.PERSONAS_DIR / f"{name}.json"
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] No persona named '{name}'.")
        raise typer.Exit(1)
    target = Path(out) if out else Path(f"{name}.persona.json")
    target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[bold green]✓ Exported '{name}' to [bold white]{target}[/bold white].[/bold green]")


def persona_import_command(file: Path):
    """Import a persona from a JSON file (name is taken from the file)."""
    if not file.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {file}")
        raise typer.Exit(1)
    try:
        p = persona_mod.Persona.from_json(file)
    except persona_mod.PersonaError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(1)
    persona_mod._ensure_dirs()
    dest = persona_mod.PERSONAS_DIR / f"{p.name}.json"
    dest.write_text(file.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[bold green]✓ Imported persona '{p.name}'.[/bold green]")


def _read_multiline(prompt: str) -> str:
    """Read multi-line input until EOF (Ctrl+D) or an empty line."""
    console.print(f"\n[bold cyan]{prompt}[/bold cyan]")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip() and lines:
            break
        lines.append(line)
    return "\n".join(lines)


def register_persona_app(app: typer.Typer) -> None:
    """Attach the persona subcommands to the given Typer app."""
    app.command("list", help="List all installed personas.")(persona_list_command)
    app.command("show", help="Show a persona's full definition.")(persona_show_command)
    app.command("templates", help="List built-in persona templates.")(persona_templates_command)
    app.command("create", help="Create a new persona.")(persona_create_command)
    app.command("edit", help="Edit a persona's system prompt.")(persona_edit_command)
    app.command("activate", help="Activate a persona.")(persona_activate_command)
    app.command("reset", help="Reset to the default assistant.")(persona_reset_command)
    app.command("delete", help="Delete a persona.")(persona_delete_command)
    app.command("export", help="Export a persona to JSON.")(persona_export_command)
    app.command("import", help="Import a persona from JSON.")(persona_import_command)
