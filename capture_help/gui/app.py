"""CaptureHelpApp — the full-screen glass chat UI for `capture-help chat`.

The interface is a two-state machine. Exactly one primary view renders at a
time, so the home dashboard and the conversation can never overlap:

    Home State (empty conversation)         Chat State (conversation)
    ┌──────────────────────────────────┐    ┌───────────────────────────
    │ ⚡ Capture Help · workspace      │    │ ⚡ Capture Help · workspace
    │……………… Landing ………………│    │ ┌──────┬──────────────────┐
    │   What would you like to build? │    │ │sidebar│ conversation  │
    │   [Explain][Fix][Generate]…     │    │ │       │ (opaque bubbles)│
    │   Recent conversations · files  │    │ │       │                │
    │ Input: "What would you like…"   │    │ │       │                │
    └──────────────────────────────────┘    │ Input: "Ask Capture Help…"
                                            └──────────────────────────

Layer stack (bottom -> top)
---------------------------
    Wallpaper   → deepest background surface, never participates in UI layout
    Dark overlay→ dimming layer between wallpaper and the glass surfaces
    Glass UI    → header, sidebar, conversation, input, footer (all opaque)
    Popup       → slash-command dropdown, modal screens
    Cursor      → Textual's own loading / toast / tooltip layers

A message landing in the conversation always enters Chat Mode first
(`_enter_chat`), so no home widget survives the transition. The provider
generators run on background threads; chunks are pushed back to the UI thread
with `call_from_thread`. Provider consoles are muted so their error prints
cannot corrupt the alternate screen.
"""

import io
import base64
import os
import re
import sys
import queue
import shutil
import subprocess
import time
import traceback
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console as RichConsole
from textual import work
from textual.app import App, ComposeResult
from textual.command import CommandPalette, Hit, Provider
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Label, Static, TextArea

from capture_help import config as config_mod
from capture_help import persona as persona_mod
from capture_help.cache import get_cached_system_prompt
from capture_help.config import settings, save_config
from capture_help.deepseek import DEEPSEEK_MODELS
from capture_help.gui.modals import (
    ConfirmScreen,
    ContextViewerScreen,
    ImagePathScreen,
    ModelPickerScreen,
    PersonaPickerScreen,
    SearchModal,
    SlashHelpScreen,
)
from capture_help.gui.theme import ICONS
from capture_help.gui.tools import execute_tool, parse_tool_calls
from capture_help.gui.widgets import (
    ChatInput,
    ChatMessage,
    DebugPanel,
    EXAMPLE_PROMPTS,
    HeaderBar,
    LandingPanel,
    QUICK_ACTIONS,
    SidebarPanel,
    SlashPopup,
    StatusFooter,
    ThinkingRow,
    workspace_summary,
)
from capture_help.history import list_sessions, load_session, save_session
from capture_help.memory import add_memory, get_all_memories
from capture_help.project import fingerprint_project
from capture_help.provider import ProviderError
from capture_help.utils import get_git_diff

MAX_TOOL_TURNS = 5
CONFIRM_TIMEOUT = 120
# Used until the selected provider advertises its model limits.
DEFAULT_CONTEXT_WINDOW_TOKENS = 64_000
DEFAULT_MAX_OUTPUT_TOKENS = 8_000
STREAM_RENDER_INTERVAL = 0.06
MAX_RENDERED_CHAT_MESSAGES = 40
# Only the newest messages keep rich Markdown; older ones render as plain text.
RICH_RECENT_MESSAGES = 8
STREAM_UI_BATCH_INTERVAL = 0.10
STREAM_UI_BATCH_CHARS = 8_192
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGES_PER_MESSAGE = 3
MAX_TOTAL_IMAGE_BYTES = 30 * 1024 * 1024

# Input placeholder is scoped to the current view state.
HOME_PLACEHOLDER = "Explain code, fix bugs, or search your workspace…"
CHAT_PLACEHOLDER = "Ask Capture Help…"

SLASH_COMMANDS = [
    ("/gemma", "Switch to local Gemma 3 12B (FREE / Ollama)"),
    ("/flash", "Switch to DeepSeek V4-Flash"),
    ("/coder", "Switch to DeepSeek Coder"),
    ("/r1", "Switch to DeepSeek Reasoner R1"),
    ("/model", "View / switch the active AI model"),
    ("/persona", "Switch character persona"),
    ("/read <file>", "Load a file into context"),
    ("/run <cmd>", "Run a shell command"),
    ("/search <q>", "Search the codebase"),
    ("/diff", "Attach the current git diff"),
    ("/learn <rule>", "Teach a background memory rule"),
    ("/plan <goal>", "Create a step-by-step plan"),
    ("/clear", "Clear the conversation"),
    ("/help", "Show this menu"),
    ("/exit", "Save session and quit"),
]


class CaptureHelpCommands(Provider):
    """App-level commands surfaced in the ⌘ command palette (ctrl+shift+p)."""

    def _commands(self) -> list[Hit]:
        app = self.app
        return [
            Hit(10.0, "Ask Capture Help", app.action_focus_input, "Ask the assistant anything"),
            Hit(9.0, "New chat", app.action_new_chat, "Start a fresh conversation (ctrl+n)"),
            Hit(8.0, "Search codebase", app.action_search, "Keyword search the workspace (ctrl+k)"),
            Hit(7.0, "Clear conversation", app.action_clear_chat, "Reset the current chat (ctrl+l)"),
            Hit(6.0, "Open model picker", app.action_open_model_picker, "Switch the active AI model"),
            Hit(5.0, "Open persona picker", app.action_open_persona_picker, "Switch character persona"),
            Hit(4.0, "Open context viewer", app.action_open_context, "Inspect what the model has in context (ctrl+o)"),
            Hit(3.0, "Toggle debug panel", app.action_toggle_debug, "Show/hide the debug log (ctrl+d)"),
            Hit(2.0, "Slash command help", app.action_show_slash_help, "List available /commands"),
            Hit(1.0, "Save and quit", app.action_save_and_quit, "Persist this session and exit"),
        ]

    async def search(self, query: str) -> list[Hit]:
        q = query.lower()
        for hit in self._commands():
            if q in str(hit.match_display).lower():
                yield hit

    async def discover(self) -> list[Hit]:
        for hit in self._commands():
            yield hit


class CaptureHelpApp(App[None]):
    """Premium glass chat interface for capture-help."""

    TITLE = "Capture Help"
    SUB_TITLE = "AI Coding Assistant"
    CSS_PATH = str(Path(__file__).with_name("styles.tcss"))

    BINDINGS = [
        ("ctrl+d", "toggle_debug", "Debug panel"),
        ("ctrl+l", "clear_chat", "Clear chat"),
        ("ctrl+k", "search", "Search codebase"),
        ("ctrl+n", "new_chat", "New chat"),
        ("ctrl+c", "cancel_or_quit", "Cancel / quit"),
        ("ctrl+shift+m", "open_model_picker", "Model picker"),
        ("ctrl+p", "open_persona_picker", "Persona picker"),
        ("ctrl+o", "open_context", "Context viewer"),
    ]

    # Command palette lives on ctrl+shift+p so ctrl+p stays free for personas.
    ENABLE_COMMAND_PALETTE = True
    COMMAND_PALETTE_BINDING = "ctrl+shift+p"
    COMMANDS = {CaptureHelpCommands}

    def __init__(
        self,
        initial_messages: Optional[List[Dict[str, object]]] = None,
        session_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        try:
            self.project = fingerprint_project()
        except Exception:  # noqa: BLE001
            self.project = {"name": "project", "languages": [], "git_clean": True}

        self.initial_messages = initial_messages or []
        self.sess_id = session_id or str(uuid.uuid4())[:8]
        self.history: List[Dict[str, object]] = list(self.initial_messages)
        self._pending_images: List[str] = []
        self._hidden_chat_messages = 0
        self._context_window_tokens = DEFAULT_CONTEXT_WINDOW_TOKENS
        self._max_output_tokens = DEFAULT_MAX_OUTPUT_TOKENS
        self._pending_ui_chunks: List[str] = []
        self._last_stream_render = 0.0
        self._cached_system_prompt = get_cached_system_prompt(
            self.project.get("name", "project"), self.project.get("languages", [])
        )

        # streaming state (UI thread)
        self._current_message: Optional[ChatMessage] = None
        self._ui_text = ""
        self._thinking_row: Optional[ThinkingRow] = None
        self._thinking_timer = None
        self._gen_worker = None
        self._tool_decision_q: "queue.Queue[Optional[bool]]" = queue.Queue()

        # conversation title: heuristic fallback, refined once by the model
        self._ai_title: Optional[str] = None
        self._title_requested = False

        # last token stats, for the context viewer
        self._last_stats = None

        # application view state: exactly one of Home / Chat renders at a time
        self._in_home_view = True
        self._home_fade_pending = False

        # tool tracking
        self._open_files: List[str] = []
        self._debug_log_enabled = True

        # mute provider consoles so error prints can't corrupt the screen
        self._mute_provider_consoles()

        # widgets
        self.header: Optional[HeaderBar] = None
        self.sidebar: Optional[SidebarPanel] = None
        self.footer: Optional[StatusFooter] = None
        self.debug_panel: Optional[DebugPanel] = None

    # ------------------------------------------------------------------ #
    # Console muting
    # ------------------------------------------------------------------ #
    def _mute_provider_consoles(self) -> None:
        import capture_help.deepseek as ds
        import capture_help.providers.ollama as ol

        self._provider_log = io.StringIO()
        silent = RichConsole(file=self._provider_log, force_terminal=True, width=200)
        ds.console = silent
        ol.console = silent

    def _flush_provider_log(self) -> None:
        content = self._provider_log.getvalue()
        if content.strip() and self.debug_panel is not None:
            self._provider_log.seek(0)
            self._provider_log.truncate(0)
            self.debug_panel.write("[dim]" + content.replace("\n", " ")[:200])

    # ------------------------------------------------------------------ #
    # Compose
    # ------------------------------------------------------------------ #
    def compose(self) -> ComposeResult:
        # Bottom-most background layers. The wallpaper is the deepest surface;
        # the dark overlay sits between it and the glass UI so artwork can
        # never show through content. Both are absolute + never reflow layout.
        self.wallpaper = Static("", id="wallpaper")
        self.dark_overlay = Static("", id="dark-overlay")
        self.header = HeaderBar(self.project)
        self.sidebar = SidebarPanel()
        self.footer = StatusFooter(self.project)
        self.debug_panel = DebugPanel()
        self.landing = LandingPanel()

        yield self.wallpaper
        yield self.dark_overlay
        yield self.header
        with Horizontal(id="body"):
            yield self.sidebar
            with Vertical(id="chat-column"):
                yield self.landing
                yield ScrollableContainer(id="chat")
                with Vertical(id="input-area"):
                    yield SlashPopup(SLASH_COMMANDS)
                    with Horizontal(id="composer-row"):
                        yield ChatInput(
                            placeholder="Message Capture Help…",
                            id="prompt-input",
                        )
                        yield Button("Send ↑", id="send-prompt")
                    with Horizontal(id="composer-actions"):
                        yield Button("＋ Image", id="attach-image")
                        yield Label("", id="pending-images")
                        yield Button("Remove", id="clear-images", disabled=True)
                    yield Label(
                        "Ctrl+V paste text or image · Enter newline · Ctrl+Enter send · / commands",
                        id="prompt-hints",
                    )
            yield self.debug_panel
        yield self.footer

    def on_mount(self) -> None:
        self.query_one("#debug-panel").styles.display = "none"
        self._populate_sidebar()
        self._seed_initial_messages()
        self._populate_landing()
        self._load_default_session_preview()
        self.footer.set_model(settings.deepseek_model)
        self.footer.set_provider()
        self.footer.set_context(
            f"0 / ~{self._fmt_k(self._context_window_tokens)}"
        )
        self.footer.set_state("ready")
        self._update_pending_images()
        self._set_landing(not self.history)
        self.query_one("#prompt-input", ChatInput).focus()
        # Keep the Today's Workspace dashboard fresh while it's on screen.
        self.set_interval(60, self._refresh_workspace_tick)

    # ------------------------------------------------------------------ #
    # Initialization helpers
    # ------------------------------------------------------------------ #
    def _populate_sidebar(self) -> None:
        try:
            sessions = list_sessions()[:8]
        except Exception:  # noqa: BLE001
            sessions = []
        self.sidebar.set_recent_chats(sessions, active_id=self.sess_id)
        self.sidebar.set_open_files(self._open_files)
        try:
            memories = get_all_memories(limit=8)
        except Exception:  # noqa: BLE001
            memories = []
        self.sidebar.set_memories(memories)

    def _populate_landing(self) -> None:
        if self.landing is None:
            return
        self.landing.set_workspace(workspace_summary(self.project))

    def _refresh_workspace_tick(self) -> None:
        """Periodic dashboard refresh (git status etc. is cheap enough)."""
        if not self._in_home_view or self.landing is None:
            return
        if getattr(self, "_ws_refresh_running", False):
            return
        self._ws_refresh_running = True
        self._workspace_refresh_worker()

    @work(thread=True, exclusive=False, group="workspace")
    def _workspace_refresh_worker(self) -> None:
        try:
            summary = workspace_summary(self.project)
            try:
                self.call_from_thread(self._apply_workspace_refresh, summary)
            except Exception:  # noqa: BLE001
                pass
        finally:
            # always clear the in-flight flag so a later tick can retry
            self._ws_refresh_running = False

    def _apply_workspace_refresh(self, summary: dict) -> None:
        if self._in_home_view and self.landing is not None:
            self.landing.set_workspace(summary)

    def _recent_project_files(self) -> list:
        """Project source files, newest first, as a lightweight recent-files list."""
        root = self.project.get("root")
        if not root:
            return []
        exts = {".py", ".go", ".cpp", ".hpp", ".c", ".h", ".qml", ".lua", ".ts", ".js"}
        found = []
        try:
            for r, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__")]
                for f in files:
                    if f.endswith(tuple(exts)):
                        found.append(Path(r) / f)
                        if len(found) >= 60:
                            break
                if len(found) >= 60:
                    break
        except Exception:  # noqa: BLE001
            return []
        found.sort(key=lambda p: getattr(p.stat(), "st_mtime", 0), reverse=True)
        return found[:10]

    # ------------------------------------------------------------------ #
    # Application state machine: Home <-> Chat (one view at a time)
    # ------------------------------------------------------------------ #
    _VIEW_FADE_S = 0.25

    def _set_input_placeholder(self) -> None:
        """The input is scoped to the current view: a build prompt on the home
        dashboard, a reply prompt once a conversation is active."""
        placeholder = CHAT_PLACEHOLDER if not self._in_home_view else HOME_PLACEHOLDER
        try:
            inp = self.query_one("#prompt-input", ChatInput)
        except Exception:  # noqa: BLE001
            return
        if inp.placeholder != placeholder:
            inp.placeholder = placeholder
            inp.refresh()

    def _enter_chat(self) -> None:
        """Transition to the chat view (idempotent).

        Called whenever the first message lands in the conversation so the
        home dashboard can never render alongside it.
        """
        if self._in_home_view:
            self._set_landing(False)

    def _show_home(self) -> None:
        self._set_landing(True)

    def _set_landing(self, visible: bool) -> None:
        """Swap between the home dashboard and the chat view.

        The two views are mutually exclusive: only one is ever rendered.
        Switching is immediate so no fade timers or opacity animations run.
        """
        landing = self.query_one("#landing")
        chat = self.query_one("#chat")
        self._in_home_view = visible
        self._home_fade_pending = False
        self._set_input_placeholder()
        if visible:
            chat.styles.height = "0"
            chat.styles.display = "block"
            landing.styles.display = "block"
            landing.styles.height = "1fr"
            return
        landing.styles.display = "none"
        landing.styles.height = "0"
        chat.styles.display = "block"
        chat.styles.height = "1fr"
        self._scroll_chat()

    def _finish_enter_chat(self) -> None:
        """Kept for callers that used the old fade timer."""
        if not self._in_home_view:
            self._set_landing(False)

    def _seed_initial_messages(self) -> None:
        self._render_history_messages(self.history)
        # A fresh session stays on the landing screen. Personas greet you when
        # activated via `/persona` — no auto-opened conversation here.

    def _render_history_messages(self, messages: List[Dict[str, str]]) -> None:
        visible = [
            message
            for message in messages
            if message.get("role") in ("user", "assistant")
        ]
        self._hidden_chat_messages = max(
            0, len(visible) - MAX_RENDERED_CHAT_MESSAGES
        )
        if self._hidden_chat_messages:
            self._show_history_notice()
        for message in visible[-MAX_RENDERED_CHAT_MESSAGES:]:
            self.add_message(message["role"], message.get("content", ""))
        self._compact_old_messages()

    def _compact_old_messages(self) -> None:
        chat = self.query_one("#chat", ScrollableContainer)
        messages = list(chat.query(ChatMessage))
        for message in messages[:-RICH_RECENT_MESSAGES]:
            message.compact()

    def _show_history_notice(self) -> None:
        chat = self.query_one("#chat", ScrollableContainer)
        try:
            notice = chat.query_one("#history-trim-notice", Static)
        except Exception:  # noqa: BLE001
            notice = Static("", id="history-trim-notice", markup=False)
            chat.mount(notice, before=0)
        notice.update(
            f"Showing the latest {MAX_RENDERED_CHAT_MESSAGES} messages; "
            f"{self._hidden_chat_messages} older messages remain in session history."
        )

    def _trim_chat_widgets(self) -> None:
        """Bound rendered widgets while leaving the persisted/model history intact."""
        chat = self.query_one("#chat", ScrollableContainer)
        messages = list(chat.query(ChatMessage))
        excess = len(messages) - MAX_RENDERED_CHAT_MESSAGES
        if excess > 0:
            for message in messages[:excess]:
                message.remove()
            self._hidden_chat_messages += excess
            self._show_history_notice()
            messages = messages[excess:]
        for message in messages[:-RICH_RECENT_MESSAGES]:
            message.compact()

    def _load_default_session_preview(self) -> None:
        # Left empty: recent chats are clickable from the sidebar instead.
        pass

    # ------------------------------------------------------------------ #
    # Chat helpers
    # ------------------------------------------------------------------ #
    def add_message(
        self,
        role: str,
        content: str,
        sublabel: str | None = None,
        streaming: bool = False,
    ) -> ChatMessage:
        # Any message means a conversation exists: leave the home dashboard
        # (idempotent) so the two views can never render simultaneously.
        self._enter_chat()
        chat = self.query_one("#chat", ScrollableContainer)
        msg = ChatMessage(role, content, sublabel=sublabel, streaming=streaming)
        chat.mount(msg)
        chat.scroll_end(animate=False)
        return msg

    def _scroll_chat(self) -> None:
        try:
            self.query_one("#chat", ScrollableContainer).scroll_end(animate=False)
        except Exception:  # noqa: BLE001
            pass

    def _prune_history(self) -> List[Dict[str, object]]:
        return self._prune_messages(self.history)

    def _prune_messages(
        self,
        messages: List[Dict[str, object]],
        token_budget: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """Keep the newest complete messages that fit an estimated input budget."""
        try:
            configured_budget = int(os.getenv("CAPTURE_HELP_CONTEXT_TOKENS", "0"))
        except ValueError:
            configured_budget = 0
        available = max(
            1,
            token_budget
            if token_budget is not None
            else self._context_window_tokens - self._max_output_tokens,
        )
        if configured_budget > 0:
            available = min(available, configured_budget)

        try:
            message_limit = int(os.getenv("CAPTURE_HELP_CONTEXT_MESSAGES", "0"))
        except ValueError:
            message_limit = 0

        selected = []
        used = 0
        for message in reversed(messages):
            content = str(message.get("content", ""))
            image_paths = message.get("image_paths")
            image_count = len(image_paths) if isinstance(image_paths, list) else 0
            cost = max(1, (len(content) + 2) // 3) + 4 + image_count * 1024
            remaining = available - used
            if cost > remaining:
                if not selected and remaining > 8:
                    tail_chars = max(0, (remaining - 14) * 3)
                    content = "[Earlier content truncated]\n" + content[-tail_chars:]
                    message = {**message, "content": content}
                    cost = max(1, (len(content) + 2) // 3) + 4
                else:
                    continue
            if used + cost > available:
                continue
            selected.append(message)
            used += cost
            if message_limit > 0 and len(selected) >= message_limit:
                break
        selected.reverse()
        return selected

    def _build_system_prompt(self) -> str:
        mcp_summary = ""
        try:
            from capture_help.mcp.client import available_tools_summary

            mcp_summary = available_tools_summary() or ""
        except Exception:  # noqa: BLE001
            pass
        base = self._cached_system_prompt
        if mcp_summary:
            base = f"{base}\n\n{mcp_summary}"
        return persona_mod.build_system_prompt(base)

    def _save_session(self) -> None:
        try:
            save_session(self.sess_id, self.history, title=self._ai_title)
        except Exception:  # noqa: BLE001
            pass

    def _log_debug(self, line: str) -> None:
        if self.debug_panel is not None:
            self.debug_panel.write(line)

    def _track_open_file(self, path: str) -> None:
        name = Path(path).name
        if name not in self._open_files:
            self._open_files.append(name)
            self.sidebar.set_open_files(self._open_files)

    # ------------------------------------------------------------------ #
    # Thinking / streaming UI
    # ------------------------------------------------------------------ #
    def _start_thinking(self, stage: str | None = None) -> None:
        self._stop_thinking()
        chat = self.query_one("#chat", ScrollableContainer)
        self._thinking_row = ThinkingRow(fixed_stage=stage)
        chat.mount(self._thinking_row)
        self._tick_int = 0
        self._thinking_timer = self.set_interval(0.25, self._tick_thinking)
        self.footer.set_state("thinking", streaming=True)

    def _stop_thinking(self) -> None:
        if self._thinking_timer is not None:
            self._thinking_timer.stop()
            self._thinking_timer = None
        if self._thinking_row is not None:
            try:
                self._thinking_row.remove()
            except Exception:  # noqa: BLE001
                pass
            self._thinking_row = None

    def _tick_thinking(self) -> None:
        """Advance the thinking row's stage + progress bar over ~8s, then hold
        at a done-looking state so a long generation still looks alive."""
        row = self._thinking_row
        if row is None:
            return
        if row.progress_label is not None and row.stage_label is not None:
            i = int(self._tick_int // 2)  # each frame is 0.25s
            progress = (self._tick_int % 16) / 16.0 if self._tick_int < 100 else 0.9
            row.set_stage(i)
            row.set_progress(progress)
        self._tick_int += 1

    # ------------------------------------------------------------------ #
    # Streaming worker (runs in a background thread)
    # ------------------------------------------------------------------ #
    def _get_provider(self, notify_fallback: bool = True):
        from capture_help.deepseek import DeepSeekProvider
        from capture_help.providers.ollama import OllamaProvider

        model = settings.deepseek_model
        base = settings.deepseek_base_url
        prov = settings.default_provider
        is_local = (
            prov == "ollama"
            or ":" in model.lower()
            or "localhost" in base.lower()
            or "127.0.0.1" in base.lower()
            or "11434" in base.lower()
        )
        if is_local:
            return OllamaProvider(model=model, base_url=base)
        key = settings.deepseek_api_key
        if not key or len(key) < 10 or "test" in key.lower():
            if notify_fallback:
                self.call_from_thread(self._fallback_to_local)
            return OllamaProvider(model="gemma3:12b", base_url="http://localhost:11434/v1")
        return DeepSeekProvider(model=model)

    def _fallback_to_local(self) -> None:
        save_config(api_key="", provider="ollama", model="gemma3:12b", keep_key=True)
        self.notify("DeepSeek key missing/invalid — switched to local Gemma 3 (FREE).", severity="warning")
        self.footer.set_model("gemma3:12b")
        self._log_debug("[yellow]Fallback[/yellow] -> local Gemma 3 12B")

    @work(thread=True, exclusive=False, group="generate")
    def _generate(self, messages: List[Dict[str, object]], system_prompt: str) -> None:
        try:
            provider = self._get_provider()
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self._on_error, f"Could not initialize provider: {e}")
            return

        context_window = DEFAULT_CONTEXT_WINDOW_TOKENS
        max_output = DEFAULT_MAX_OUTPUT_TOKENS
        get_limits = getattr(provider, "get_context_limits", None)
        if get_limits is not None:
            try:
                limits = get_limits()
                if limits is not None:
                    context_window, max_output = limits
                    self.call_from_thread(
                        self._set_context_limits, context_window, max_output
                    )
            except Exception as e:  # noqa: BLE001
                self.call_from_thread(
                    self._log_debug,
                    f"[yellow]Context metadata unavailable; using estimated "
                    f"{self._fmt_k(context_window)} token window: {e}[/yellow]",
                )
        input_budget = max(
            128,
            context_window - max_output - (len(system_prompt) + 2) // 3,
        )
        pruned = self._prune_messages(messages, token_budget=input_budget)

        turn = 0
        while turn <= MAX_TOOL_TURNS:
            try:
                if (
                    any(message.get("image_paths") for message in pruned)
                    and "api.deepseek.com"
                    in str(getattr(provider, "base_url", "")).lower()
                    and "flash" not in str(getattr(provider, "model", "")).lower()
                ):
                    raise ProviderError(
                        "Image input requires a vision-capable model. "
                        "Select DeepSeek V4-Flash or a vision model in Ollama."
                    )
                provider_messages = self._encode_image_messages(pruned)
                gen = provider.stream_completion(provider_messages, system_prompt)
                reply_parts = []
                ui_batch = []
                ui_batch_chars = 0
                last_ui_flush = time.monotonic()
                for chunk, stats in gen:
                    if chunk:
                        reply_parts.append(chunk)
                        ui_batch.append(chunk)
                        ui_batch_chars += len(chunk)
                        now = time.monotonic()
                        if (
                            ui_batch_chars >= STREAM_UI_BATCH_CHARS
                            or now - last_ui_flush >= STREAM_UI_BATCH_INTERVAL
                        ):
                            self.call_from_thread(self._on_token, "".join(ui_batch))
                            ui_batch.clear()
                            ui_batch_chars = 0
                            last_ui_flush = now
                    if stats:
                        self.call_from_thread(self._on_stats, stats)
                if ui_batch:
                    self.call_from_thread(self._on_token, "".join(ui_batch))
                reply = "".join(reply_parts)
            except ProviderError as e:
                self.call_from_thread(self._on_error, str(e))
                return
            except SystemExit:
                self.call_from_thread(self._on_error, "Provider configuration error — fix and try again.")
                return
            except Exception as e:  # noqa: BLE001
                self.call_from_thread(self._on_error, f"API Error: {e}")
                return

            self.call_from_thread(self._on_turn_done, reply)
            self._flush_provider_log_threadsafe()

            if turn >= MAX_TOOL_TURNS:
                break
            calls = parse_tool_calls(reply)
            if not calls:
                break

            # Tools can take seconds (builds, searches): keep the UI alive with
            # a pinned progress card that fills in ✓ lines as tools finish.
            self.call_from_thread(self._start_thinking, "Running tools…")

            try:
                outputs: List[str] = []
                for kind, payload in calls:
                    out = self._execute_tool_blocking(kind, payload, reply)
                    display = payload if not isinstance(payload, tuple) else payload[0]
                    outputs.append(out)
                    self.call_from_thread(self._on_tool_output, kind, display, out)
            except Exception as e:  # noqa: BLE001
                # Never leave the pinned "Running tools…" card stuck on screen.
                self.call_from_thread(self._on_error, f"Tool execution failed: {e}")
                return

            self.call_from_thread(
                self.history.append,
                {"role": "user", "content": f"Tool Output:\n{chr(10).join(outputs)[:20_000]}"},
            )
            self._save_session_threadsafe()
            pruned = self._prune_history_threadsafe(input_budget)
            turn += 1
        self.call_from_thread(self._on_generation_finished)

    def _execute_tool_blocking(self, kind: str, payload, reply: str) -> str:
        if kind == "run":
            if not self._confirm_tool(f"Execute command?\n\n{payload}"):
                return "Action cancelled by user."
            return execute_tool("run", payload)
        if kind == "write":
            if isinstance(payload, tuple) and len(payload) == 2:
                target, content = payload
            else:
                target = payload
                content = self._extract_code_block(reply)
            if not content.strip():
                return "Error: no code block found to write for this TOOL_WRITE."
            if not self._confirm_tool(f"Write file?\n\n{target}\n\n{content[:200]}"):
                return "Action cancelled by user."
            return execute_tool("write", (target, content))
        return execute_tool(kind, payload)

    def _confirm_tool(self, message: str) -> bool:
        self.call_from_thread(self._ask_confirmation, message)
        try:
            return bool(self._tool_decision_q.get(timeout=CONFIRM_TIMEOUT))
        except queue.Empty:
            return False

    def _ask_confirmation(self, message: str) -> None:
        self.push_screen(ConfirmScreen(message), lambda yes: self._tool_decision_q.put(bool(yes)))

    @staticmethod
    def _extract_code_block(text: str) -> str:
        blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        return blocks[-1].strip() if blocks else ""

    # -- helper callbacks (UI thread) -- #
    def _on_token(self, chunk: str) -> None:
        if self._current_message is None:
            self._stop_thinking()
            self._current_message = self.add_message(
                "assistant", "", streaming=True
            )
            self._last_stream_render = time.monotonic()
        self._pending_ui_chunks.append(chunk)
        now = time.monotonic()
        if now - self._last_stream_render >= STREAM_RENDER_INTERVAL:
            self._flush_streaming_text()
        elif self._current_message.stream_preview is None:
            self.call_after_refresh(self._flush_streaming_text)

    def _flush_streaming_text(self) -> None:
        if not self._pending_ui_chunks:
            return
        if (
            self._current_message is not None
            and self._current_message.stream_preview is None
        ):
            return
        self._ui_text += "".join(self._pending_ui_chunks)
        self._pending_ui_chunks.clear()
        self._last_stream_render = time.monotonic()
        if self._current_message is None:
            return
        self._current_message.update_stream_preview(self._ui_text)
        self._scroll_chat()

    def _finalize_streaming_message(self) -> None:
        self._flush_streaming_text()
        if self._current_message is not None:
            self._current_message.finalize_stream(self._ui_text)

    def _set_context_limits(self, context_window: int, max_output: int) -> None:
        self._context_window_tokens = context_window
        self._max_output_tokens = max_output
        last_stats = self._last_stats
        used = int(getattr(last_stats, "prompt_tokens", 0) or 0)
        self.footer.set_context(
            f"{self._fmt_k(used)} / {self._fmt_k(self._context_window_tokens)}"
        )

    def _write_crash_report(self, error: Exception) -> None:
        """Persist an unhandled Textual exception for local diagnosis."""
        try:
            log_path = config_mod.CONFIG_DIR / "logs" / "gui-crash.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            report = (
                f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"session={self.sess_id}\n"
                + "".join(
                    traceback.format_exception(
                        type(error), error, error.__traceback__
                    )
                )
            )
            report = re.sub(
                r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}",
                "[REDACTED_API_KEY]",
                report,
            )
            if log_path.exists() and log_path.stat().st_size > 1_000_000:
                previous = log_path.read_text(encoding="utf-8", errors="replace")
                log_path.write_text(previous[-500_000:], encoding="utf-8")
            with log_path.open("a", encoding="utf-8") as log:
                log.write(report)
        except OSError as log_error:
            sys.__stderr__.write(f"Could not write Capture Help crash log: {log_error}\n")

    def _handle_exception(self, error: Exception) -> None:
        """Log an unhandled UI error and preserve the interactive session."""
        self._write_crash_report(error)
        self._save_session()
        try:
            self.notify(
                "Unexpected UI error; the chat is still open. "
                "See ~/.config/capture-help/logs/gui-crash.log.",
                severity="error",
                timeout=10,
            )
        except Exception as notification_error:  # noqa: BLE001
            sys.__stderr__.write(
                f"Capture Help UI error: {error}\n"
                f"Could not show error notification: {notification_error}\n"
            )

    def _on_stats(self, stats) -> None:
        self._last_stats = stats
        self.footer.set_stats(stats)
        if getattr(stats, "prompt_tokens", 0):
            self.footer.set_context(
                f"{self._fmt_k(stats.prompt_tokens)} / "
                f"{self._fmt_k(self._context_window_tokens)}"
            )
        if getattr(stats, "cache_hit_tokens", 0):
            self._log_debug(f"[dim]cache hit[/dim] {stats.cache_hit_tokens} tokens")

    @staticmethod
    def _fmt_k(tokens: int) -> str:
        """Compact token count: 2300 -> '2.3k', 32000 -> '32k', 320 -> '320'."""
        if tokens < 1000:
            return f"{tokens}"
        value = tokens / 1000
        if value == int(value):
            return f"{int(value)}k"
        return f"{value:.1f}k"

    def _on_turn_done(self, reply: str) -> None:
        self._finalize_streaming_message()
        self._stop_thinking()
        if self._current_message is not None:
            self._current_message = None
        self._ui_text = ""
        self._pending_ui_chunks.clear()
        self.history.append({"role": "assistant", "content": reply})
        self._save_session()
        self._maybe_generate_title()
        self.call_after_refresh(self._trim_chat_widgets)

    # -- AI conversation titles -- #
    def _maybe_generate_title(self) -> None:
        """Kick off a best-effort, one-shot title refinement for this session.

        Runs in a background thread after the first assistant reply so the
        sidebar shows a descriptive title instead of the raw first prompt.
        The heuristic title from ``save_session`` stays until this lands, and
        every failure path falls back to it silently.
        """
        if self._title_requested:
            return
        self._title_requested = True
        if len(self.history) < 2:
            return
        if not any(m.get("role") == "assistant" for m in self.history):
            return
        if not any(m.get("role") == "user" for m in self.history):
            return
        self._title_worker(self.sess_id)

    @work(thread=True, exclusive=False, group="title")
    def _title_worker(self, sess_id: str) -> None:
        # Snapshot history on the UI thread (never read a live list from a
        # worker) and build the provider without the missing-key fallback
        # side effects — the generation worker already handled those.
        try:
            snapshot = self.call_from_thread(lambda: [dict(m) for m in self.history])
        except Exception:  # noqa: BLE001
            return
        first_user = next(
            (m.get("content", "") for m in snapshot if m.get("role") == "user"), ""
        ).strip()
        first_asst = next(
            (m.get("content", "") for m in snapshot if m.get("role") == "assistant"), ""
        ).strip()
        if not first_user:
            return
        try:
            provider = self._get_provider(notify_fallback=False)
        except Exception:  # noqa: BLE001
            return
        messages = [
            {
                "role": "user",
                "content": f"User: {first_user[:300]}\n\nAssistant: {first_asst[:300]}",
            }
        ]
        system = (
            "Create a short, descriptive title (2-6 words) for this coding "
            "conversation. Reply with ONLY the title: no quotes, no punctuation, "
            "no markdown."
        )
        title = ""
        try:
            gen = provider.stream_completion(messages, system, temperature=0.2)
            for chunk, _ in gen:
                if chunk:
                    title += chunk
                    if len(title) > 200:
                        break
        except Exception:  # noqa: BLE001
            return
        title = self._sanitize_title(title)
        if title:
            try:
                self.call_from_thread(self._apply_title, sess_id, title)
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _sanitize_title(text: str) -> str:
        title = (text or "").strip().strip('"\'`').strip()
        title = title.splitlines()[0].strip() if title else ""
        if title.lower().startswith("title:"):
            title = title[6:].strip()
        title = title.rstrip(".:;!?-")
        return title[:48]

    def _apply_title(self, sess_id: str, title: str) -> None:
        if self.sess_id != sess_id or not title:
            return
        self._ai_title = title
        self._save_session()
        self._populate_sidebar()

    def _on_tool_output(self, kind: str, display, out: str) -> None:
        icon = {"run": "⚡", "read": "▤", "search": "⌕", "write": "✎", "mcp": "⇄"}.get(kind, "⚙")
        short = out if len(out) < 1200 else out[:1200] + "\n…"
        sublabel = {"run": "🐚 Terminal", "read": "▤ File", "search": "⌕ Search",
                    "write": "✎ Write", "mcp": "⇄ MCP"}.get(kind)
        self.add_message("tool", f"{icon} {display}\n{short}", sublabel=sublabel)
        self._log_debug(f"[cyan]{icon} tool {kind}:[/cyan] {display}")
        if kind in ("read", "write"):
            self._track_open_file(str(display))
        # reflect completed work in the pinned thinking card, if it is showing
        if self._thinking_row is not None:
            verb = {"run": "Ran", "read": "Read", "search": "Searched",
                    "write": "Wrote", "mcp": "Called"}.get(kind, "Ran")
            cancelled = "Action cancelled by user." in (out or "")
            if cancelled:
                self._thinking_row.add_done(f"{display} (cancelled)", warn=True)
            else:
                self._thinking_row.add_done(f"{verb} {display}")

    def _on_generation_finished(self) -> None:
        self._stop_thinking()
        self._current_message = None
        self._ui_text = ""
        self.footer.set_state("ready")
        self._save_session()
        self._flush_provider_log()

    def _on_error(self, msg: str) -> None:
        self._finalize_streaming_message()
        self._stop_thinking()
        self._current_message = None
        self._ui_text = ""
        self._pending_ui_chunks.clear()
        self.footer.set_state("error")
        self.add_message("error", msg)
        self._log_debug(f"[red]Error:[/red] {msg}")
        self._flush_provider_log()

    # -- thread-safe variants for state used from the worker -- #
    def _flush_provider_log_threadsafe(self) -> None:
        self.call_from_thread(self._flush_provider_log)

    def _save_session_threadsafe(self) -> None:
        self.call_from_thread(self._save_session)

    def _prune_history_threadsafe(self, token_budget: int) -> List[Dict[str, object]]:
        return self.call_from_thread(
            lambda: self._prune_messages(self.history, token_budget=token_budget)
        )

    # ------------------------------------------------------------------ #
    # Input handling
    # ------------------------------------------------------------------ #
    def _submit_prompt(self, value: str) -> None:
        inp = self.query_one("#prompt-input", ChatInput)
        if inp.id != "prompt-input":
            return
        popup = self._popup()
        if popup is not None and popup.is_visible():
            cmd = popup.selected()
            if cmd:
                inp.value = cmd + " "
                inp.cursor_position = len(inp.value)
                popup.hide()
                inp.focus()
                return
        text = value.strip()
        if self._gen_worker is not None and self._gen_worker.is_running:
            self.notify(
                "Still generating — wait for the current reply to finish.",
                severity="warning",
            )
            return
        if not text and not self._pending_images:
            return
        inp.value = ""
        if popup is not None:
            popup.hide()
        images = list(self._pending_images)
        self._pending_images.clear()
        self._update_pending_images()
        if not text and images:
            text = "Please analyze the attached image."
        if text.startswith("/") or text.lower() in ("help", "exit", "quit", "clear"):
            status = self._handle_slash(text)
            if status is not None:
                return
        self._send(text, image_paths=images)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Keep the slash popup in sync as the user types."""
        if event.text_area.id != "prompt-input":
            return
        value = event.text_area.text
        popup = self._popup()
        if popup is None:
            return
        if value.startswith("/"):
            count = popup.show(value)
            if self.debug_panel is not None and self.debug_panel.visible:
                self._log_debug(f"[magenta]slash[/magenta] {value!r} -> {count} match(es)")
        else:
            popup.hide()

    # ------------------------------------------------------------------ #
    # Sidebar: load a saved conversation
    # ------------------------------------------------------------------ #
    def on_option_list_option_selected(self, event) -> None:
        opt_id = getattr(event.option, "id", None)
        if opt_id and opt_id.startswith("session:"):
            self._load_session(opt_id[len("session:"):])

    def _load_session(self, sid: str) -> None:
        """Open a saved conversation from the sidebar into the chat view."""
        if self._gen_worker is not None and self._gen_worker.is_running:
            self.notify("Wait for the current reply to finish first.", severity="warning")
            return
        data = load_session(sid)
        if not data:
            self.notify("Could not load that session.", severity="warning")
            return
        messages = data.get("messages") or []
        self.history = [dict(m) for m in messages]
        self._pending_images.clear()
        self._update_pending_images()
        self.sess_id = sid
        self._ai_title = data.get("title") or None
        # the loaded title is final — don't regenerate a new one
        self._title_requested = True
        chat = self.query_one("#chat", ScrollableContainer)
        chat.remove_children()
        self._hidden_chat_messages = 0
        self._render_history_messages(self.history)
        self._enter_chat()
        self._populate_sidebar()
        self._save_session()  # bump it to the top of the list
        title = data.get("title") or sid
        self.notify(f"Loaded: {title}")

    def _popup(self) -> SlashPopup | None:
        try:
            return self.query_one("#slash-popup", SlashPopup)
        except Exception:  # noqa: BLE001
            return None

    def _send(self, text: str, image_paths: Optional[List[str]] = None) -> None:
        if self._gen_worker is not None and self._gen_worker.is_running:
            self.notify("Still generating — wait for the current reply to finish.", severity="warning")
            return
        self._remember_correction(text)
        self._enter_chat()
        message = {"role": "user", "content": text}
        if image_paths:
            message["image_paths"] = image_paths
            names = ", ".join(Path(path).name for path in image_paths)
            text = f"{text}\n\n📎 {names}"
            message["content"] = text
        self.history.append(message)
        self.add_message("user", text)
        self._save_session()
        self._current_message = None
        self._ui_text = ""
        self._start_thinking()
        self._gen_worker = self._generate(
            [dict(message) for message in self.history],
            self._build_system_prompt(),
        )

    def _validate_image_path(self, value: str) -> str:
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Image file not found: {path}")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError("Images must be 10 MiB or smaller.")
        with path.open("rb") as image_file:
            header = image_file.read(12)
        if not self._image_mime_type(header):
            raise ValueError("Choose a valid PNG, JPEG, GIF, or WebP image.")
        return str(path)

    @staticmethod
    def _image_mime_type(header: bytes) -> Optional[str]:
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if header.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return "image/webp"
        return None

    def _read_clipboard_image(self) -> Optional[tuple[bytes, str]]:
        supported_types = ("image/png", "image/jpeg", "image/webp", "image/gif")
        if shutil.which("wl-paste"):
            try:
                clipboard_types = subprocess.run(
                    ["wl-paste", "--list-types"],
                    check=True,
                    capture_output=True,
                    timeout=1.5,
                    text=True,
                ).stdout.splitlines()
                for mime_type in supported_types:
                    if mime_type in clipboard_types:
                        image = subprocess.run(
                            ["wl-paste", "--type", mime_type, "--no-newline"],
                            check=True,
                            capture_output=True,
                            timeout=2.0,
                        ).stdout
                        return image, mime_type
            except (OSError, subprocess.SubprocessError):
                pass

        if shutil.which("xclip"):
            try:
                clipboard_types = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                    check=True,
                    capture_output=True,
                    timeout=1.5,
                    text=True,
                ).stdout.splitlines()
                for mime_type in supported_types:
                    if mime_type in clipboard_types:
                        image = subprocess.run(
                            ["xclip", "-selection", "clipboard", "-t", mime_type, "-o"],
                            check=True,
                            capture_output=True,
                            timeout=2.0,
                        ).stdout
                        return image, mime_type
            except (OSError, subprocess.SubprocessError):
                pass
        return None

    def _paste_clipboard_image(self) -> bool:
        clipboard_image = self._read_clipboard_image()
        if clipboard_image is None:
            return False
        image_bytes, mime_type = clipboard_image
        actual_mime_type = self._image_mime_type(image_bytes[:12])
        if not image_bytes or actual_mime_type != mime_type:
            self.notify("The clipboard image has an unsupported or invalid format.", severity="error")
            return True
        self._attach_image_bytes(image_bytes, actual_mime_type)
        return True

    def _attach_image_bytes(self, image_bytes: bytes, mime_type: str) -> None:
        actual_mime_type = self._image_mime_type(image_bytes[:12])
        if not actual_mime_type or actual_mime_type != mime_type:
            self.notify("Choose a valid PNG, JPEG, GIF, or WebP image.", severity="error")
            return
        if len(image_bytes) > MAX_IMAGE_BYTES:
            self.notify("Images must be 10 MiB or smaller.", severity="error")
            return
        if len(self._pending_images) >= MAX_IMAGES_PER_MESSAGE:
            self.notify(
                f"Attach up to {MAX_IMAGES_PER_MESSAGE} images per message.",
                severity="warning",
            )
            return
        extension = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }[mime_type]
        attachment_dir = config_mod.CONFIG_DIR / "history" / "attachments"
        image_path = attachment_dir / f"{uuid.uuid4().hex}{extension}"
        try:
            attachment_dir.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(image_bytes)
        except OSError as error:
            self.notify(f"Could not save clipboard image: {error}", severity="error")
            return
        self._pending_images.append(str(image_path))
        self._update_pending_images()
        self.notify("Image pasted")

    def _encode_image_messages(self, messages: List[Dict[str, object]]) -> List[dict]:
        encoded = []
        total_image_bytes = 0
        for message in messages:
            image_paths = message.get("image_paths") or []
            if not image_paths:
                encoded.append(dict(message))
                continue
            if not isinstance(image_paths, list) or not all(
                isinstance(image_path, str) for image_path in image_paths
            ):
                raise ProviderError("Saved image attachment references are invalid.")
            parts = [{"type": "text", "text": str(message.get("content", ""))}]
            for image_path in image_paths:
                path = Path(image_path)
                try:
                    if path.stat().st_size > MAX_IMAGE_BYTES:
                        raise ProviderError(
                            f"Attached image exceeds 10 MiB: {path}"
                        )
                    image_bytes = path.read_bytes()
                except OSError as error:
                    raise ProviderError(
                        f"Attached image is no longer available: {path}"
                    ) from error
                total_image_bytes += len(image_bytes)
                if total_image_bytes > MAX_TOTAL_IMAGE_BYTES:
                    raise ProviderError(
                        "Attached images exceed the 30 MiB total request limit. "
                        "Start a new chat or remove older image turns."
                    )
                mime_type = self._image_mime_type(image_bytes[:12])
                if not mime_type or len(image_bytes) > MAX_IMAGE_BYTES:
                    raise ProviderError(
                        f"Attached image is invalid or exceeds 10 MiB: {path}"
                    )
                data_url = (
                    f"data:{mime_type};base64,"
                    f"{base64.b64encode(image_bytes).decode('ascii')}"
                )
                parts.append(
                    {"type": "image_url", "image_url": {"url": data_url}}
                )
            encoded.append({"role": message["role"], "content": parts})
        return encoded

    def _on_image_path(self, value: Optional[str]) -> None:
        if not value:
            return
        try:
            path = self._validate_image_path(value)
        except (OSError, ValueError) as error:
            self.notify(str(error), severity="error")
            return
        if path in self._pending_images:
            self.notify("That image is already attached.")
            return
        if len(self._pending_images) >= MAX_IMAGES_PER_MESSAGE:
            self.notify(
                f"Attach up to {MAX_IMAGES_PER_MESSAGE} images per message.",
                severity="warning",
            )
            return
        self._pending_images.append(path)
        self._update_pending_images()
        self.notify(f"Attached {Path(path).name}")

    def action_clear_pending_images(self) -> None:
        self._pending_images.clear()
        self._update_pending_images()

    def _update_pending_images(self) -> None:
        label = self.query_one("#pending-images", Label)
        clear_button = self.query_one("#clear-images", Button)
        count = len(self._pending_images)
        label.update(f"📎 {count} image{'s' if count != 1 else ''}" if count else "")
        clear_button.disabled = not count
        clear_button.display = bool(count)

    def _remember_correction(self, text: str) -> None:
        """Learn only unmistakable user corrections, not ordinary chat content."""
        if not re.match(
            r"^\s*(?:no[,.!:]\s|i meant\b|i said\b|correction\s*:|"
            r"that(?:'s| is) (?:wrong|incorrect)\b|"
            r"you misunderstood\b|the correct (?:answer|version|way)\b)",
            text,
            re.IGNORECASE,
        ):
            return
        learned = add_memory("auto_correction", f"User correction: {text}")
        if learned:
            self._cached_system_prompt = get_cached_system_prompt(
                self.project.get("name", "project"),
                self.project.get("languages", []),
            )
            self._populate_sidebar()
            self.notify("Saved your correction to local memory.")

    # ------------------------------------------------------------------ #
    # Landing screen interactions
    # ------------------------------------------------------------------ #
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "attach-image":
            self.push_screen(ImagePathScreen(), self._on_image_path)
        elif button_id == "clear-images":
            self.action_clear_pending_images()
        elif button_id == "send-prompt":
            self._submit_prompt(self.query_one("#prompt-input", ChatInput).text)
        elif button_id == "sidebar-new-chat":
            self.action_new_chat()
        elif button_id == "sidebar-search":
            self.action_search()
        elif button_id == "qa-primary":
            # The hero action: focus the input and let the user type a prompt.
            # No toast — the input placeholder and the hint line beneath it
            # already explain what to do.
            self.query_one("#prompt-input", ChatInput).focus()
        elif button_id.startswith("chip-"):
            try:
                text = EXAMPLE_PROMPTS[int(button_id.split("-", 1)[1])]
            except (ValueError, IndexError):
                return
            inp = self.query_one("#prompt-input", ChatInput)
            inp.value = text
            inp.focus()
        elif button_id.startswith("qa-"):
            self._run_quick_action(button_id.split("-", 1)[1])

    def _run_quick_action(self, key: str) -> None:
        if key == "search":
            self.action_search()
            return
        if key == "git":
            diff = get_git_diff()
            if not diff:
                self.add_message("warning", "No git diff detected.")
                return
            self.add_message("tool", f"⎇ Git diff ({len(diff.splitlines())} lines)\n\n{diff[:1500]}")
            self.history.append({"role": "user", "content": f"Git diff:\n```diff\n{diff[:20_000]}\n```"})
            self._save_session()
            return
        prompt = dict((a[0], a[2]) for a in QUICK_ACTIONS).get(key)
        if prompt:
            self._send(prompt)

    # ------------------------------------------------------------------ #
    # Slash commands
    # ------------------------------------------------------------------ #
    def _accept_slash_command(self) -> None:
        """Fill the input with the currently highlighted command (or /model)."""
        popup = self._popup()
        if popup is not None and popup.is_visible():
            cmd = popup.selected()
            if cmd:
                inp = self.query_one("#prompt-input", ChatInput)
                inp.value = cmd + " "
                inp.cursor_position = len(inp.value)
                inp.focus()
            popup.hide()
            return
        self.action_open_model_picker()

    def _handle_slash(self, text: str):
        """Return True if consumed, False to fall through to normal send, None to ignore."""
        parts = text.strip().split(maxsplit=1)
        sub = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if sub in ("/exit", "exit", "quit"):
            self._save_session()
            self.notify(f"Session saved ({self.sess_id}). Goodbye!")
            self.exit()
            return True

        if sub in ("/clear", "clear"):
            self.history = []
            self._pending_images.clear()
            self._update_pending_images()
            self.sess_id = str(uuid.uuid4())[:8]
            self._ai_title = None
            self._title_requested = False
            self.query_one("#chat", ScrollableContainer).remove_children()
            self._show_home()
            self.footer.set_stats(None)
            self.notify("Chat cleared.")
            return True

        if sub in ("/help", "help"):
            self.push_screen(SlashHelpScreen(SLASH_COMMANDS))
            return True

        if sub == "/model":
            if arg:
                return True if self._switch_model(arg.strip().lower()) else None
            options = [
                (key, data["name"], data.get("description", "")[:50], key == settings.deepseek_model)
                for key, data in DEEPSEEK_MODELS.items()
            ]
            self.push_screen(
                ModelPickerScreen(DEEPSEEK_MODELS, current=settings.deepseek_model),
                self._on_model_picked,
            )
            return True

        if sub in ("/persona", "/character"):
            if arg:
                self._activate_persona(arg.strip())
                return True
            options = [("default", "Standard AI Assistant", "Default coding assistant", False)]
            active = persona_mod.get_active_persona()
            active_name = active.name if active else None
            for p in persona_mod.list_personas():
                options.append((p.name, p.display_name, (p.description or "")[:50], p.name == active_name))
            self.push_screen(
                PersonaPickerScreen(options, active_name=active_name),
                self._on_persona_picked,
            )
            return True

        if sub in ("/gemma", "/gemma12b"):
            return self._switch_model("gemma3:12b")
        if sub == "/gemma27b":
            return self._switch_model("gemma3:27b")
        if sub in ("/flash", "/cheap"):
            return self._switch_model("deepseek-v4-flash")
        if sub == "/coder":
            return self._switch_model("deepseek-coder")
        if sub in ("/r1", "/reasoner"):
            return self._switch_model("deepseek-reasoner")

        if sub == "/read":
            if not arg:
                self.notify("Usage: /read <filepath>", severity="warning")
                return True
            from capture_help.gui.tools import execute_tool

            result = execute_tool("read", arg)
            self.add_message("tool", f"▤ {arg}\n\n{result[:1500]}")
            self.history.append({"role": "user", "content": f"File content '{arg}':\n{result[:30_000]}"})
            self._save_session()
            return True

        if sub == "/run":
            if not arg:
                self.notify("Usage: /run <command>", severity="warning")
                return True
            if not self._confirm_tool(f"Execute command?\n\n{arg}"):
                return True
            from capture_help.gui.tools import execute_tool

            out = execute_tool("run", arg)
            self.add_message("tool", f"⚡ {arg}\n\n{out[:1500]}")
            self.history.append({"role": "user", "content": f"Terminal output of `{arg}`:\n{out[:20_000]}"})
            self._save_session()
            return True

        if sub == "/search":
            if not arg:
                self.notify("Usage: /search <query>", severity="warning")
                return True
            from capture_help.gui.tools import execute_tool

            result = execute_tool("search", arg)
            self.add_message("tool", f"⌕ {arg}\n\n{result[:1500]}")
            self.history.append({"role": "user", "content": f"Search results for '{arg}':\n{result[:20_000]}"})
            self._save_session()
            return True

        if sub == "/diff":
            diff = get_git_diff()
            if not diff:
                self.add_message("warning", "No git diff detected.")
                return True
            self.add_message("tool", f"⎇ Git diff ({len(diff.splitlines())} lines)\n\n{diff[:1500]}")
            self.history.append({"role": "user", "content": f"Git diff:\n```diff\n{diff[:20_000]}\n```"})
            self._save_session()
            return True

        if sub in ("/learn", "/memory"):
            from capture_help.memory import add_memory, get_all_memories

            if arg:
                add_memory("user_preference", arg)
                self._populate_sidebar()
                self.notify(f"Learned: {arg}")
            else:
                memories = get_all_memories()
                if not memories:
                    self.add_message("system", "No background memories saved.")
                else:
                    lines = "\n".join(f"• {m['content']}" for m in memories)
                    self.add_message("tool", f"🧠 Learned rules ({len(memories)})\n\n{lines}")
            return True

        if sub in ("/scan", "/virus"):
            self.notify("Run `capture-help scan` in your terminal.", severity="warning")
            return True

        if sub in ("/plan", "/goal"):
            goal = arg or "Plan step-by-step implementation"
            self.history.append(
                {"role": "user", "content": f"Create a concise step-by-step plan for: {goal}."}
            )
            self.add_message("user", f"🎯 {goal}")
            self._save_session()
            return False

        if sub == "/mcp":
            self.notify("MCP tools are injected automatically when configured.", severity="information")
            return True

        return False

    # ------------------------------------------------------------------ #
    # Modal callbacks
    # ------------------------------------------------------------------ #
    def _on_model_picked(self, key) -> None:
        if key:
            self._switch_model(key)

    def _on_persona_picked(self, key) -> None:
        if not key:
            return
        if key == "default":
            persona_mod.reset_persona()
            self.notify("Persona reset to default assistant.")
        else:
            self._activate_persona(key)

    def _switch_model(self, key: str) -> bool:
        data = DEEPSEEK_MODELS.get(key)
        if not data:
            return False
        is_local = "gemma" in key
        prov = "ollama" if is_local else "deepseek"
        url = "http://localhost:11434/v1" if is_local else "https://api.deepseek.com"
        if not is_local and (not settings.deepseek_api_key or len(settings.deepseek_api_key) < 10 or "test" in settings.deepseek_api_key.lower()):
            self.notify(f"'{data['name']}' needs a DeepSeek API key — staying on local Gemma.", severity="warning")
            return True
        save_config(api_key=settings.deepseek_api_key or "ollama", base_url=url, model=key, provider=prov)
        self.notify(f"Active model: {data['name']} ({key})")
        self.footer.set_model(key)
        self._log_debug(f"[cyan]model[/cyan] -> {key}")
        return True

    def _activate_persona(self, name: str) -> None:
        try:
            p = persona_mod.activate_persona(name)
        except persona_mod.PersonaError as e:
            self.notify(str(e), severity="error")
            return
        self.notify(f"Persona active: {p.display_name}")
        self._log_debug(f"[cyan]persona[/cyan] -> {p.display_name}")
        if getattr(p, "first_message", None):
            self.history.append({"role": "assistant", "content": p.first_message})
            self.add_message("assistant", p.first_message)
            self._save_session()

    # ------------------------------------------------------------------ #
    # Key bindings
    # ------------------------------------------------------------------ #
    def action_toggle_debug(self) -> None:
        panel = self.query_one("#debug-panel")
        panel.styles.display = "none" if panel.styles.display == "block" else "block"

    def action_open_model_picker(self) -> None:
        self.push_screen(
            ModelPickerScreen(DEEPSEEK_MODELS, current=settings.deepseek_model),
            self._on_model_picked,
        )

    def action_open_persona_picker(self) -> None:
        options = [("default", "Standard AI Assistant", "Default coding assistant", False)]
        active = persona_mod.get_active_persona()
        active_name = active.name if active else None
        for p in persona_mod.list_personas():
            options.append((p.name, p.display_name, (p.description or "")[:50], p.name == active_name))
        self.push_screen(
            PersonaPickerScreen(options, active_name=active_name),
            self._on_persona_picked,
        )

    def action_open_context(self) -> None:
        """Inspect what the model currently has in context (Ctrl+O)."""
        hist_chars = sum(len(m.get("content", "")) for m in self.history)
        last = getattr(self, "_last_stats", None)
        prompt_tokens = int(getattr(last, "prompt_tokens", 0) or 0)
        self.push_screen(
            ContextViewerScreen(
                session_id=self.sess_id,
                title=self._ai_title or "",
                open_files=list(self._open_files),
                prompt_tokens=prompt_tokens,
                window_tokens=self._context_window_tokens,
                history_chars=hist_chars,
            )
        )

    def action_focus_input(self) -> None:
        self.query_one("#prompt-input", ChatInput).focus()

    def action_show_slash_help(self) -> None:
        self.push_screen(SlashHelpScreen(SLASH_COMMANDS))

    def action_save_and_quit(self) -> None:
        self._save_session()
        self.exit()

    def action_clear_chat(self) -> None:
        self.history = []
        self._pending_images.clear()
        self._update_pending_images()
        self.query_one("#chat", ScrollableContainer).remove_children()
        self._show_home()
        self.footer.set_stats(None)
        self.notify("Conversation cleared.")

    def action_new_chat(self) -> None:
        self._save_session()
        self.history = []
        self._pending_images.clear()
        self._update_pending_images()
        self.sess_id = str(uuid.uuid4())[:8]
        self._ai_title = None
        self._title_requested = False
        self.query_one("#chat", ScrollableContainer).remove_children()
        self._populate_landing()
        self._show_home()
        self.notify(f"New session ({self.sess_id}).")

    def action_search(self) -> None:
        self.push_screen(SearchModal(), self._on_search_query)

    def _on_search_query(self, query) -> None:
        if query:
            self._search_worker(query)

    @work(thread=True, group="search")
    def _search_worker(self, query: str) -> None:
        result = execute_tool("search", query)
        self.call_from_thread(self._on_search_done, query, result)

    def _on_search_done(self, query: str, result: str) -> None:
        self.add_message("tool", f"⌕ {query}\n\n{result[:1500]}")
        self._log_debug(f"[cyan]search[/cyan] {query}")

    def action_cancel_or_quit(self) -> None:
        if self._gen_worker is not None and self._gen_worker.is_running:
            self.workers.cancel_group(self, "generate")
            self._stop_thinking()
            self.footer.set_state("cancelled")
            self.notify("Generation cancelled.")
        else:
            self._save_session()
            self.exit()
