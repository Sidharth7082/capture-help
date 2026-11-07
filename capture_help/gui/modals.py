"""Textual modal screens replacing the old prompt_toolkit selectors."""

from typing import List, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option


class BaseModal(ModalScreen):
    """Shared styling + hint for capture-help modals."""

    BINDINGS = [("escape", "dismiss_modal", "Cancel")]

    def __init__(self, title: str = "", **kwargs):
        super().__init__(**kwargs)
        self.title_text = title

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


class ModelPickerScreen(BaseModal):
    """Arrow-key / mouse model selector built from DEEPSEEK_MODELS."""

    def __init__(self, models: dict, current: str = "", **kwargs):
        super().__init__("Select AI Model", **kwargs)
        self.models = models
        self.current = current

    def compose(self) -> ComposeResult:
        options = []
        for key, data in self.models.items():
            label = f"{data.get('name', key)}  —  {data.get('description', '')[:48]}"
            is_current = key == self.current
            if is_current:
                label = f"{label}   ✓ active"
            options.append(Option(label, id=key))
        with Vertical(classes="modal-card"):
            yield Label(f"{self.title_text}", classes="modal-title")
            yield OptionList(*options, id="model-options")
            yield Label("↑/↓ navigate · Enter select · Esc cancel", classes="modal-hint")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class ConfirmScreen(BaseModal):
    """Yes/No confirmation used before executing commands or writing files."""

    def __init__(self, message: str, title: str = "Confirm Action", **kwargs):
        super().__init__(title, **kwargs)
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-card"):
            yield Label(f"⚠️ {self.title_text}", classes="modal-title")
            yield Static(self.message, markup=False)
            with Horizontal(classes="modal-buttons"):
                yield Button("Yes", id="btn-yes")
                yield Button("No", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")


class SearchModal(BaseModal):
    """Quick codebase keyword search."""

    def __init__(self, **kwargs):
        super().__init__("Search Project Codebase", **kwargs)

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-card"):
            yield Label("⌕ Search Project Codebase", classes="modal-title")
            yield Input(placeholder="Keywords... (e.g. glass effect, signal handler)", id="search-input")
            yield Label("Enter to search · Esc to cancel", classes="modal-hint")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())


class ImagePathScreen(BaseModal):
    """Ask for a local image path to attach to the next prompt."""

    def __init__(self, **kwargs):
        super().__init__("Attach Image", **kwargs)

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-card"):
            yield Label("Attach a local image", classes="modal-title")
            yield Input(placeholder="/path/to/image.png", id="image-path-input")
            yield Label(
                "PNG, JPEG, GIF, or WebP · sent to your selected AI provider",
                classes="modal-hint",
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())


class ContextViewerScreen(BaseModal):
    """What the model currently has in context: session, open files, usage."""

    def __init__(
        self,
        session_id: str = "",
        title: str = "",
        open_files: Optional[List[str]] = None,
        prompt_tokens: int = 0,
        window_tokens: int = 0,
        history_chars: int = 0,
        **kwargs,
    ):
        super().__init__("Context", **kwargs)
        self.session_id = session_id
        self.title = title
        self.open_files = open_files or []
        self.prompt_tokens = prompt_tokens
        self.window_tokens = window_tokens
        self.history_chars = history_chars

    def compose(self) -> ComposeResult:
        est = self.history_chars // 4
        pct = int(self.prompt_tokens / self.window_tokens * 100) if self.window_tokens else 0
        lines = [
            f"Session: {self.session_id}",
            f"Title:   {self.title or '—'}",
            "",
            f"Token usage: {self.prompt_tokens:,} / {self.window_tokens:,}  ({pct}%)",
            f"History: ~{est:,} tokens in the conversation",
            "",
            "Open files:",
        ]
        lines += [f"  ▸ {f}" for f in self.open_files[:20]] or ["  (none yet)"]
        with Vertical(classes="modal-card"):
            yield Label("🧠 Context", classes="modal-title")
            yield Static("\n".join(lines), markup=False)
            yield Label("Esc to close", classes="modal-hint")


class SlashHelpScreen(BaseModal):
    """Overview of available slash commands."""

    def __init__(self, commands: List[tuple], **kwargs):
        super().__init__("Slash Commands", **kwargs)
        self.commands = commands

    def compose(self) -> ComposeResult:
        lines = "\n".join(f"{cmd:<24} {desc}" for cmd, desc in self.commands)
        with Vertical(classes="modal-card"):
            yield Label("⚡ Slash Commands", classes="modal-title")
            yield Static(lines, markup=False)
            yield Label("Esc to close", classes="modal-hint")

    def on_key(self, event) -> None:
        if event.key in ("escape", "q", "ctrl+c"):
            self.dismiss(None)
            event.stop()
