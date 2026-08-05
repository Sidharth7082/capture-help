"""Custom Textual widgets for the Capture Help glass UI."""

from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.widgets import Button, Collapsible, Input, Label, Markdown, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from capture_help import __version__
from capture_help.config import settings
from capture_help.deepseek import DEEPSEEK_MODELS
from capture_help.gui import theme

ROLE_ICONS = {
    "user": "◆",
    "assistant": "✦",
    "tool": "⚙",
    "error": "✕",
    "warning": "⚠",
    "system": "·",
}

# --------------------------------------------------------------------------- #
# Identity helpers
# --------------------------------------------------------------------------- #
def model_display_name(key: str | None = None) -> str:
    """Friendly model name, e.g. `deepseek-v4-flash` -> `DeepSeek V4 Flash`."""
    key = key or settings.deepseek_model
    data = DEEPSEEK_MODELS.get(key)
    if data:
        return data["name"]
    return key.replace("-", " ").replace(":", " ").title()


def provider_display_name() -> str:
    prov = settings.default_provider
    if prov == "ollama":
        return "Ollama (Local)"
    if prov and prov != "deepseek":
        return prov.title()
    return "DeepSeek"


TAGLINE = "Fast  •  Private  •  Open Source"

# --------------------------------------------------------------------------- #
# Chat widgets
# --------------------------------------------------------------------------- #
class ChatMessage(Container):
    """A single conversation bubble.

    Roles: user / assistant / tool / error / warning / system.
    Assistant bubbles embed a Markdown widget that can be updated in place
    while tokens stream in.
    """

    def __init__(self, role: str, content: str = "", streaming: bool = False, **kwargs):
        classes = f"chat-message role-{role}"
        super().__init__(classes=classes, **kwargs)
        self.role = role
        self.content = content
        self.streaming = streaming
        self.markdown: Markdown | None = None

    def compose(self) -> ComposeResult:
        with Container(classes="bubble"):
            if self.role in ("user", "assistant"):
                self.markdown = Markdown(self.content or "")
                yield self.markdown
            else:
                icon = ROLE_ICONS.get(self.role, "·")
                text = f"{icon} {self.content}" if self.content else icon
                yield Static(text, markup=False)

    def update_markdown(self, text: str) -> None:
        if self.markdown is not None:
            self.markdown.update(text)


class ThinkingRow(Container):
    """Streaming placeholder shown while a reply is being generated."""

    def __init__(self, **kwargs):
        super().__init__(id="thinking-row", **kwargs)
        self.label: Label | None = None

    def compose(self) -> ComposeResult:
        self.label = Label("✦ Thinking", id="thinking-label")
        yield self.label


class HeaderBar(Vertical):
    """Product hero + workspace metadata. Capture Help's own identity strip."""

    def __init__(self, project: dict, **kwargs):
        super().__init__(id="app-header", **kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="hero-title-block"):
            yield Label(f"{theme.ICONS['bolt']} Capture Help", id="app-title")
            yield Label("Local AI Coding Assistant", id="app-subtitle")
            yield Label(TAGLINE, id="app-tagline")

        # Workspace info grid: Project · Languages · Git · Model · Provider
        with Grid(id="workspace-grid", classes="workspace-grid"):
            langs = self.project.get("languages", []) or []
            git_clean = self.project.get("git_clean", True)
            git_text = f"{theme.ICONS['git']} ✓ Clean" if git_clean else f"{theme.ICONS['git']} ✗ Modified"
            git_cls = "wp-value wp-git-clean" if git_clean else "wp-value wp-git-dirty"

            for label, value, value_cls in (
                ("Project", self.project.get("name", "project"), "wp-value"),
                ("Languages", "  •  ".join(langs[:4]) or "—", "wp-value"),
                ("Git", git_text, git_cls),
                ("Model", model_display_name(), "wp-value wp-accent"),
                ("Provider", provider_display_name(), "wp-value"),
            ):
                with Vertical(classes="wp-field"):
                    yield Label(label.upper(), classes="wp-label")
                    yield Label(value, classes=value_cls)


class StatusFooter(Horizontal):
    """Status bar: runtime identity (left) + live streaming stats (right)."""

    def __init__(self, project: dict | None = None, **kwargs):
        super().__init__(id="status-footer", **kwargs)
        self.project = project or {}
        self.model_label: Label | None = None
        self.provider_label: Label | None = None
        self.context_label: Label | None = None
        self.git_label: Label | None = None
        self.version_label: Label | None = None
        self.tokens_label: Label | None = None
        self.time_label: Label | None = None
        self.cost_label: Label | None = None
        self.state_label: Label | None = None

    def compose(self) -> ComposeResult:
        git_clean = self.project.get("git_clean", True)
        git_text = f"{theme.ICONS['git']} ✓ Clean" if git_clean else f"{theme.ICONS['git']} ✗ Modified"
        git_cls = "status-item git-clean" if git_clean else "status-item git-dirty"

        self.model_label = Label("", classes="status-item model")
        self.provider_label = Label("", classes="status-item")
        self.context_label = Label("", classes="status-item")
        self.git_label = Label(git_text, classes=git_cls)
        self.version_label = Label(f"v{__version__}", classes="status-item version")
        self.tokens_label = Label("", classes="status-item")
        self.time_label = Label("", classes="status-item")
        self.cost_label = Label("", classes="status-item cost")
        self.state_label = Label("", classes="status-item")

        yield self.model_label
        yield self.provider_label
        yield self.context_label
        yield self.git_label
        yield self.version_label
        yield Label("", classes="status-spacer")
        yield self.tokens_label
        yield self.time_label
        yield self.cost_label
        yield self.state_label

    def set_model(self, model: str) -> None:
        if self.model_label:
            self.model_label.update(f"{theme.ICONS['model']}  {model_display_name(model)}")

    def set_provider(self, provider: str | None = None) -> None:
        if self.provider_label:
            self.provider_label.update(provider or provider_display_name())

    def set_context(self, text: str) -> None:
        if self.context_label:
            self.context_label.update(f"Context {text}")

    def set_stats(self, stats) -> None:
        if not stats:
            return
        if self.tokens_label:
            self.tokens_label.update(f"{theme.ICONS['tokens']}  {stats.total_tokens:,} tok")
        if self.time_label:
            self.time_label.update(f"{theme.ICONS['time']}  {stats.duration_seconds:.1f}s")
        if self.cost_label:
            self.cost_label.update(f"{theme.ICONS['cost']}  ${stats.cost_usd:.5f}")

    def set_state(self, text: str, streaming: bool = False) -> None:
        if not self.state_label:
            return
        cls = "status-item state-streaming" if streaming else "status-item"
        self.state_label.update(text)
        self.state_label.set_classes(cls)

    def on_click(self, event) -> None:
        """Clicking the model label opens the model picker."""
        if event.widget is self.model_label:
            action = getattr(self.app, "action_open_model_picker", None)
            if action is not None:
                action()


class SidebarPanel(Vertical):
    """Left sidebar: recent chat sessions and files touched in this session."""

    def __init__(self, **kwargs):
        super().__init__(id="sidebar", **kwargs)
        self.recent_list: OptionList | None = None
        self.open_files: Vertical | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="sidebar-section"):
            yield Label("RECENT CONVERSATIONS", classes="sidebar-section-title")
            self.recent_list = OptionList(id="recent-chats")
            yield self.recent_list
        with Vertical(classes="sidebar-section"):
            yield Label("RECENT FILES", classes="sidebar-section-title")
            self.open_files = Vertical(id="open-files")
            yield self.open_files

    def set_recent_chats(self, sessions: list) -> None:
        if not self.recent_list:
            return
        self.recent_list.clear_options()
        if not sessions:
            self.recent_list.add_option(Option("(no saved conversations)", id="none"))
            return
        for s in sessions:
            sid = str(s.get("id", ""))
            title = s.get("title", "Chat Session")[:30]
            turns = s.get("turns", 0)
            self.recent_list.add_option(Option(f"{title}  · {turns}t", id=f"session:{sid}"))

    def set_open_files(self, files: list) -> None:
        if not self.open_files:
            return
        self.open_files.remove_children()
        if not files:
            self.open_files.mount(Label("(none yet)", classes="sidebar-item"))
            return
        for f in files[:20]:
            self.open_files.mount(Label(f"▸ {f}", classes="sidebar-item"))


class DebugPanel(Vertical):
    """Collapsible debug/log panel, hidden by default (Ctrl+D to toggle)."""

    def __init__(self, **kwargs):
        super().__init__(id="debug-panel", **kwargs)
        self.rich_log: RichLog | None = None

    def compose(self) -> ComposeResult:
        with Collapsible(title="🐞 Debug & Logs", collapsed=True):
            self.rich_log = RichLog(id="debug-log", highlight=True, markup=True, wrap=True)
            yield self.rich_log

    def write(self, line: str) -> None:
        if self.rich_log is not None:
            self.rich_log.write(line)


# --------------------------------------------------------------------------- #
# Landing screen (empty state)
# --------------------------------------------------------------------------- #
EXAMPLE_PROMPTS = [
    "Explain renderer.cpp...",
    "Fix build errors...",
    "Generate documentation...",
    "Refactor my project...",
]

QUICK_ACTIONS = [
    ("explain", "⌘ Explain Code", "Explain the core architecture and key components of this project."),
    ("fix", "⌘ Fix Errors", "Find and fix build and runtime errors in this project."),
    ("search", "⌘ Search Project", "__SEARCH__"),
    ("review", "⌘ Review Changes", "Review my current uncommitted git changes and suggest improvements."),
    ("docs", "⌘ Generate Docs", "Generate thorough documentation for this project."),
    ("git", "⌘ Git Summary", "__DIFF__"),
]


class LandingPanel(Vertical):
    """The empty-state landing screen.

    Hero question, clickable example prompts, keyboard-navigable quick actions
    and recent conversations / files. It fades away once a conversation begins.
    """

    def __init__(self, **kwargs):
        super().__init__(id="landing", **kwargs)
        self.recent_list: OptionList | None = None
        self.recent_files: Vertical | None = None

    def compose(self) -> ComposeResult:
        yield Label("What would you like to build today?", id="landing-question")
        yield Label("Choose a starting point to get going", id="landing-sub")

        with Grid(id="example-row", classes="example-row"):
            for i, text in enumerate(EXAMPLE_PROMPTS):
                yield Button(text, id=f"chip-{i}", classes="chip")

        yield Label("Quick Actions", classes="section-label")
        with Grid(id="qa-grid"):
            for key, label, _ in QUICK_ACTIONS:
                yield Button(label, id=f"qa-{key}", classes="qa-btn")

        with Horizontal(classes="landing-columns"):
            with Vertical(classes="landing-col"):
                yield Label("Recent Conversations", classes="section-label")
                self.recent_list = OptionList(id="landing-recent")
                yield self.recent_list
            with Vertical(classes="landing-col"):
                yield Label("Recent Files", classes="section-label")
                self.recent_files = Vertical(id="landing-files")
                yield self.recent_files

    def set_recent_chats(self, sessions: list) -> None:
        if not self.recent_list:
            return
        self.recent_list.clear_options()
        if not sessions:
            self.recent_list.add_option(Option("(no saved conversations)", id="none"))
            return
        for s in sessions[:8]:
            sid = str(s.get("id", ""))
            title = s.get("title", "Chat Session")[:26]
            turns = s.get("turns", 0)
            self.recent_list.add_option(Option(f"• {title}   · {turns}t", id=f"session:{sid}"))

    def set_recent_files(self, files: list) -> None:
        if not self.recent_files:
            return
        self.recent_files.remove_children()
        if not files:
            self.recent_files.mount(Label("(none yet)", classes="landing-file-item"))
            return
        for f in files[:10]:
            self.recent_files.mount(Label(f"• {f}", classes="landing-file-item"))


# --------------------------------------------------------------------------- #
# Slash-command discovery
# --------------------------------------------------------------------------- #
class SlashPopup(Vertical):
    """Autocomplete dropdown of slash commands shown above the prompt input.

    Typing ``/`` in the input pops this up (via ``show``). Filtering, arrow-key
    navigation and selection are driven by the app + ``ChatInput`` so that
    keyboard focus always stays in the input while the user narrows their query.
    """

    def __init__(self, commands: list, **kwargs):
        super().__init__(id="slash-popup", **kwargs)
        self.all_commands = commands
        self.option_list: OptionList | None = None

    def compose(self) -> ComposeResult:
        self.option_list = OptionList(id="slash-options")
        yield self.option_list

    def _matches(self, value: str) -> list:
        prefix = value.lstrip().lower()
        if not prefix:
            return list(self.all_commands)
        return [
            (cmd, desc)
            for cmd, desc in self.all_commands
            if cmd.startswith(prefix) or prefix in desc.lower()
        ]

    def show(self, value: str) -> int:
        """Repopulate with commands matching ``value`` and reveal if any match."""
        matches = self._matches(value)
        if self.option_list is None:
            return 0
        self.option_list.clear_options()
        for cmd, desc in matches:
            self.option_list.add_option(Option(f"{cmd}  —  {desc}", id=cmd))
        visible = bool(matches)
        self.styles.display = "block" if visible else "none"
        if matches:
            self.option_list.highlighted = 0
        return len(matches)

    def hide(self) -> None:
        self.styles.display = "none"

    def is_visible(self) -> bool:
        return self.styles.display != "none"

    def move(self, delta: int) -> None:
        if self.option_list is None:
            return
        count = len(self.option_list.options)
        if not count:
            return
        idx = self.option_list.highlighted
        idx = 0 if idx is None else idx
        self.option_list.highlighted = (idx + delta) % count

    def selected(self) -> str | None:
        """The id (command string) of the highlighted option, if any."""
        if self.option_list is None:
            return None
        opt = self.option_list.highlighted_option
        return getattr(opt, "id", None)


class ChatInput(Input):
    """Prompt input that keeps the slash popup in sync while typing.

    Arrow keys move the popup highlight and Escape/Tab dismiss or fill it, but
    focus stays in the input so the user can keep typing to narrow the list.
    ``Enter`` is left to ``Input.Submitted`` and handled by the app.
    """

    def _popup(self) -> SlashPopup | None:
        try:
            return self.app.query_one("#slash-popup", SlashPopup)
        except Exception:
            return None

    def _accept_tab(self) -> None:
        popup = self._popup()
        if popup is None:
            return
        cmd = popup.selected()
        if cmd:
            self.value = cmd + " "
            self.cursor_position = len(self.value)
        popup.hide()
        self.focus()

    async def _on_key(self, event) -> None:
        popup = self._popup()
        if popup is not None and popup.is_visible():
            if event.key == "down":
                popup.move(1)
                event.stop()
                event.prevent_default()
                return
            if event.key == "up":
                popup.move(-1)
                event.stop()
                event.prevent_default()
                return
            if event.key == "escape":
                popup.hide()
                event.stop()
                event.prevent_default()
                return
            if event.key == "tab":
                self._accept_tab()
                event.stop()
                event.prevent_default()
                return
        await super()._on_key(event)