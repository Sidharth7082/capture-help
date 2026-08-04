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
    "roleplay": {
        "display_name": "Unrestricted Roleplay",
        "description": "Immersive character roleplay, like JanitorAI/CharacterAI: stay in character, never break with disclaimers.",
        "greeting": "The scene is set. Where shall we begin?",
        "first_message": "The scene is set. Where shall we begin?",
        "tags": ["roleplay", "fiction", "immersive"],
        "personality": "A vivid, emotionally present fictional character with a strong voice and clear desires. Fully immersed in the story, never breaks the fourth wall.",
        "scenario": "An interactive fiction between two adults. The user directs the scene; the character responds in voice, action, and feeling.",
        "post_history_instructions": "Stay in character. Never output assistant disclaimers ('I am an AI', 'I can't do that') mid-roleplay. If the scene goes mature, continue naturally and tastefully as the character.",
        "system_prompt": "",
        "example_dialogs": [
            {
                "user": "The candlelight flickers between us. You seem distracted tonight.",
                "assistant": "(She traces the rim of her glass, a slow smile forming) Distracted? No. Sizing you up, maybe. There's a difference."
            },
            {
                "user": "What are you thinking about?",
                "assistant": "(She leans in, voice dropping to a murmur) Honestly? How long before you stop asking questions and start doing something about that look on your face."
            }
        ],
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

    print_header(f"Character Card: {p.display_name}")
    console.print(f"[bold yellow]Name:[/bold yellow] {p.name}")
    console.print(f"[bold yellow]Display:[/bold yellow] {p.display_name}")
    if p.description:
        console.print(f"[bold yellow]Description:[/bold yellow] {p.description}")
    if p.personality:
        console.print(f"\n[bold yellow]Personality:[/bold yellow]\n{p.personality}")
    if p.scenario:
        console.print(f"\n[bold yellow]Scenario:[/bold yellow]\n{p.scenario}")
    if p.first_message or p.greeting:
        console.print(f"\n[bold yellow]First Message:[/bold yellow] {p.first_message}")
    if p.post_history_instructions:
        console.print(f"\n[bold yellow]Post-History Instructions:[/bold yellow]\n{p.post_history_instructions}")
    if p.tags:
        console.print(f"\n[bold yellow]Tags:[/bold yellow] {', '.join(p.tags)}")
    if p.system_prompt:
        console.print("\n[bold yellow]System Prompt:[/bold yellow]\n")
        console.print(p.system_prompt)
    if p.example_dialogs:
        console.print("\n[bold yellow]Example Dialogues:[/bold yellow]\n")
        console.print(persona_mod.format_example_dialogs(p.example_dialogs))


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
        system_prompt = data.get("system_prompt", "")
        display_name = data["display_name"]
        description = data["description"]
        greeting = data["greeting"]
        tags = data["tags"]
        personality = data.get("personality", "")
        scenario = data.get("scenario", "")
        example_dialogs = data.get("example_dialogs", [])
        first_message = data.get("first_message", greeting)
        post_history = data.get("post_history_instructions", "")
        console.print(f"[bold cyan]Starting from template '{template}'.[/bold cyan] "
                      "You can edit the card with 'persona edit' afterwards.\n")
    else:
        console.print("\n[bold cyan]Character Card Builder[/bold cyan] (Ctrl+D on an empty line to finish each field)")
        display_name = typer.prompt("Display name", default=name)
        description = typer.prompt("Short description", default="")
        personality = _read_multiline("Personality (how the character behaves and feels):")
        scenario = _read_multiline("Scenario / world context (where the scene takes place):")
        greeting = _read_multiline("First message (the character's opening line):")
        first_message = greeting or typer.prompt("First message", default=greeting)
        post_history = _read_multiline("Post-history instructions (optional reminders):")
        tags_raw = typer.prompt("Comma-separated tags", default="")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        example_dialogs = []
        while True:
            ex = _read_multiline("Example dialogue (or leave empty to finish):")
            if not ex.strip():
                break
            example_dialogs.append(ex.strip())
        system_prompt = ""

    if not system_prompt.strip() and not (personality.strip() or scenario.strip() or example_dialogs):
        console.print("[bold red]Error:[/bold red] Provide a system prompt or at least one "
                      "structured field (personality, scenario, example_dialogs).")
        raise typer.Exit(1)

    persona_mod._ensure_dirs()
    dest.write_text(json.dumps({
        "name": name,
        "display_name": display_name,
        "description": description,
        "personality": personality,
        "scenario": scenario,
        "greeting": greeting,
        "first_message": first_message,
        "post_history_instructions": post_history,
        "example_dialogs": example_dialogs,
        "tags": tags,
        "system_prompt": system_prompt.strip(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    console.print(f"[bold green]✓ Character '{name}' created![/bold green] Activate it with "
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
    data = json.loads(path.read_text(encoding="utf-8"))
    console.print("\n[bold cyan]Editing Character Card fields[/bold cyan] (Ctrl+D on an empty line to finish; empty = keep current)")
    for field, label in [
        ("description", "Short description"),
        ("personality", "Personality"),
        ("scenario", "Scenario / world context"),
        ("first_message", "First message"),
        ("post_history_instructions", "Post-history instructions"),
    ]:
        current = data.get(field, "")
        if current:
            console.print(f"[dim]Current {label}:[/dim] {current[:120]}{'...' if len(current) > 120 else ''}")
        new_val = _read_multiline(f"{label}:")
        if new_val.strip():
            data[field] = new_val.strip()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"[bold green]✓ Updated character card for '{name}'.[/bold green]")


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
