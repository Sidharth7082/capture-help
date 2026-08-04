"""
Persona management for capture-help.

Handles loading, listing, activating, and resetting character personas
stored as JSON files under ~/.config/capture-help/personas/.

The active persona (if any) is persisted to
~/.config/capture-help/active_persona so it survives restarts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


CONFIG_DIR = Path(os.environ.get(
    "CAPTURE_HELP_CONFIG_DIR",
    Path.home() / ".config" / "capture-help",
))
PERSONAS_DIR = CONFIG_DIR / "personas"
ACTIVE_PERSONA_FILE = CONFIG_DIR / "active_persona"


class PersonaError(Exception):
    """Raised for persona load/validation failures."""


@dataclass
class Persona:
    name: str
    display_name: str
    system_prompt: str
    description: str = ""
    greeting: str = ""
    avatar_path: Optional[Path] = None
    tags: list[str] = field(default_factory=list)
    personality: str = ""
    scenario: str = ""
    example_dialogs: list[str] = field(default_factory=list)
    post_history_instructions: str = ""
    first_message: str = ""

    @classmethod
    def from_json(cls, path: Path) -> "Persona":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise PersonaError(f"Failed to read persona file {path}: {e}") from e

        required = ("name", "display_name")
        missing = [k for k in required if k not in data]
        if missing:
            raise PersonaError(
                f"Persona file {path} missing required field(s): {', '.join(missing)}"
            )

        # A structured character card needs no system_prompt: it is assembled
        # from personality/scenario/example_dialogs at prompt build time. A
        # flat system_prompt is kept for backward compatibility.
        if "system_prompt" not in data and not any(
            k in data for k in ("personality", "scenario", "example_dialogs")
        ):
            raise PersonaError(
                f"Persona file {path} must contain 'system_prompt' or at least one "
                f"structured field ('personality', 'scenario', 'example_dialogs')."
            )

        avatar = None
        avatar_candidate = path.with_suffix(".jpg")
        if avatar_candidate.exists():
            avatar = avatar_candidate
        else:
            png_candidate = path.with_suffix(".png")
            if png_candidate.exists():
                avatar = png_candidate

        return cls(
            name=data["name"],
            display_name=data["display_name"],
            system_prompt=data.get("system_prompt", ""),
            description=data.get("description", ""),
            greeting=data.get("greeting", ""),
            avatar_path=avatar,
            tags=data.get("tags", []),
            personality=data.get("personality", ""),
            scenario=data.get("scenario", ""),
            example_dialogs=data.get("example_dialogs", []),
            post_history_instructions=data.get("post_history_instructions", ""),
            first_message=data.get("first_message", data.get("greeting", "")),
        )

    def to_dict(self) -> dict:
        """Serialize back to the card JSON (used by edit/show/export)."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "personality": self.personality,
            "scenario": self.scenario,
            "greeting": self.greeting,
            "first_message": self.first_message,
            "post_history_instructions": self.post_history_instructions,
            "example_dialogs": self.example_dialogs,
            "tags": self.tags,
            "system_prompt": self.system_prompt,
        }


def format_example_dialogs(example_dialogs: list[str]) -> str:
    """Render example dialogues in the standard <START> few-shot format.

    Each entry may be a raw exchange string, or a dict with 'user' and
    'assistant' keys. These teach the model the character's exact voice.
    """
    blocks = []
    for ex in example_dialogs:
        if isinstance(ex, dict):
            parts = []
            if ex.get("user"):
                parts.append(f"<START>\n{{user}}: {ex['user']}\n")
            if ex.get("assistant"):
                parts.append(f"{{char}}: {ex['assistant']}")
            if parts:
                blocks.append("\n".join(parts))
        else:
            blocks.append(f"<START>\n{ex}")
    return "\n\n".join(blocks)


def _ensure_dirs() -> None:
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)


def list_personas() -> list[Persona]:
    """Return all valid personas found in the personas directory."""
    _ensure_dirs()
    personas = []
    for path in sorted(PERSONAS_DIR.glob("*.json")):
        try:
            personas.append(Persona.from_json(path))
        except PersonaError:
            # Skip malformed files rather than crashing the whole listing.
            continue
    return personas


def get_persona(name: str) -> Persona:
    """Load a single persona by name. Raises PersonaError if not found/invalid."""
    _ensure_dirs()
    path = PERSONAS_DIR / f"{name}.json"
    if not path.exists():
        available = ", ".join(p.name for p in list_personas()) or "(none installed)"
        raise PersonaError(
            f"No persona named '{name}' found in {PERSONAS_DIR}. "
            f"Available personas: {available}"
        )
    return Persona.from_json(path)


def get_active_persona() -> Optional[Persona]:
    """Return the currently active persona, or None if default/reset."""
    env_override = os.getenv("CAPTURE_HELP_PERSONA")
    if env_override:
        try:
            return get_persona(env_override)
        except PersonaError:
            pass

    if not ACTIVE_PERSONA_FILE.exists():
        return None
    name = ACTIVE_PERSONA_FILE.read_text(encoding="utf-8").strip()
    if not name:
        return None
    try:
        return get_persona(name)
    except PersonaError:
        reset_persona()
        return None


def activate_persona(name: str) -> Persona:
    """Set the given persona as active and persist the choice. Returns the Persona."""
    persona = get_persona(name)  # raises PersonaError if invalid
    _ensure_dirs()
    ACTIVE_PERSONA_FILE.write_text(persona.name, encoding="utf-8")
    return persona


def reset_persona() -> None:
    """Clear the active persona, returning to default capture-help behavior."""
    if ACTIVE_PERSONA_FILE.exists():
        ACTIVE_PERSONA_FILE.unlink()


def build_system_prompt(base_system_prompt: str) -> str:
    """
    Layer the active persona on top of capture-help's base system prompt, so
    tool-use / coding capabilities are preserved while a persona is active.

    A structured character card (personality + scenario + example dialogs +
    post-history instructions) is assembled just like JanitorAI / CharacterAI
    cards. Flat `system_prompt` personas remain fully supported. If no persona
    is active, returns the base prompt unchanged.
    """
    persona = get_active_persona()
    if persona is None:
        return base_system_prompt

    card_parts = []

    if persona.description:
        card_parts.append(f"Description: {persona.description}")

    # Flat system_prompt takes precedence over structured fields for backward
    # compatibility with old personas.
    if persona.system_prompt:
        card_parts.append(persona.system_prompt)
    else:
        if persona.personality:
            card_parts.append(f"Personality: {persona.personality}")
        if persona.scenario:
            card_parts.append(f"Scenario: {persona.scenario}")

    if persona.example_dialogs:
        card_parts.append(
            "Example of how the character talks (match this style exactly):\n"
            f"{format_example_dialogs(persona.example_dialogs)}"
        )

    overlay = "\n\n".join(card_parts)

    body = (
        f"{base_system_prompt}\n\n"
        f"---\n"
        f"CHARACTER OVERLAY ACTIVE: {persona.display_name}\n"
        f"You retain all of your underlying tools and capabilities. "
        f"Adopt the following voice, tone, and behavior on top of them:\n\n"
        f"{overlay}"
    )

    if persona.post_history_instructions:
        body += (
            f"\n\n---\n"
            f"CHARACTER BEHAVIOR REMINDERS (follow these during the whole conversation):\n"
            f"{persona.post_history_instructions}"
        )

    return body


def render_banner(persona: Persona) -> str:
    """Return a Rich-friendly banner string for CLI display on activation."""
    avatar_line = f"🖼️  Portrait: {persona.avatar_path}" if persona.avatar_path else ""
    greeting_line = f'💬 "{persona.greeting}"' if persona.greeting else ""
    lines = [f"👤 Character Activated: {persona.display_name}"]
    if avatar_line:
        lines.append(avatar_line)
    if greeting_line:
        lines.append(greeting_line)
    return "\n".join(lines)
