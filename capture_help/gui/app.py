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
import os
import re
import sys
import queue
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console as RichConsole
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Input, Label, Static

from capture_help import persona as persona_mod
from capture_help.cache import get_cached_system_prompt
from capture_help.config import settings, save_config
from capture_help.deepseek import DEEPSEEK_MODELS
from capture_help.gui.modals import (
    ConfirmScreen,
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
from capture_help.project import fingerprint_project
from capture_help.provider import ProviderError
from capture_help.utils import get_git_diff

MAX_TOOL_TURNS = 5
CONFIRM_TIMEOUT = 120

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
    ]

    # The slash popup + model/persona pickers provide discoverability; the
    # built-in command palette is disabled so ctrl+p is free for personas.
    ENABLE_COMMAND_PALETTE = False

    def __init__(
        self,
        initial_messages: Optional[List[Dict[str, str]]] = None,
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
        self.history: List[Dict[str, str]] = list(self.initial_messages)
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
                    yield ChatInput(
                        placeholder=HOME_PLACEHOLDER,
                        id="prompt-input",
                    )
                    yield Label(
                        "Type / for commands"
                        f"   {ICONS['search']} Ctrl+K Search"
                        f"   {ICONS['clear']} Ctrl+L Clear"
                        f"   {ICONS['debug']} Ctrl+D Debug"
                        f"   {ICONS['model']} Ctrl+Shift+M Model",
                        classes="sidebar-item",
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
        self.footer.set_context("8k / 32k")
        self.footer.set_state("ready")
        self._set_landing(not self.history)
        self.query_one("#prompt-input", ChatInput).focus()
        # Gentle entrance: fade the chrome in over ~350ms.
        for selector in ("#app-header", "#sidebar", "#status-footer"):
            try:
                w = self.query_one(selector)
                w.styles.opacity = 0.0
                w.styles.animate("opacity", 1.0, duration=0.35)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ #
    # Initialization helpers
    # ------------------------------------------------------------------ #
    def _populate_sidebar(self) -> None:
        try:
            sessions = list_sessions()[:8]
        except Exception:  # noqa: BLE001
            sessions = []
        self.sidebar.set_recent_chats(sessions)
        self.sidebar.set_open_files(self._open_files)

    def _populate_landing(self) -> None:
        if self.landing is None:
            return
        self.landing.set_workspace(workspace_summary(self.project))

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
        Entering chat fades the dashboard out over ``_VIEW_FADE_S`` seconds
        and then hard-collapses it, so no home widgets remain in the layout.
        """
        landing = self.query_one("#landing")
        chat = self.query_one("#chat")
        self._in_home_view = visible
        self._set_input_placeholder()
        if visible:
            self._home_fade_pending = False
            chat.styles.height = "0"
            chat.styles.display = "block"
            chat.styles.opacity = 0.0
            landing.styles.display = "block"
            landing.styles.height = "1fr"
            landing.styles.opacity = 1.0
            return
        if self._home_fade_pending:
            return
        landing.styles.opacity = 0.0
        self._home_fade_pending = True
        self.set_timer(self._VIEW_FADE_S, self._finish_enter_chat)

    def _finish_enter_chat(self) -> None:
        try:
            landing = self.query_one("#landing")
            chat = self.query_one("#chat")
        except Exception:  # noqa: BLE001
            return
        if self._in_home_view or not self._home_fade_pending:
            return
        self._home_fade_pending = False
        landing.styles.display = "none"
        landing.styles.height = "0"
        landing.styles.opacity = 1.0
        chat.styles.display = "block"
        chat.styles.height = "1fr"
        chat.styles.opacity = 1.0
        self._scroll_chat()

    def _seed_initial_messages(self) -> None:
        for m in self.history:
            if m.get("role") in ("user", "assistant"):
                self.add_message(m["role"], m.get("content", ""))
        # A fresh session stays on the landing screen. Personas greet you when
        # activated via `/persona` — no auto-opened conversation here.

    def _load_default_session_preview(self) -> None:
        # Left empty: recent chats are clickable from the sidebar instead.
        pass

    # ------------------------------------------------------------------ #
    # Chat helpers
    # ------------------------------------------------------------------ #
    def add_message(self, role: str, content: str) -> ChatMessage:
        # Any message means a conversation exists: leave the home dashboard
        # (idempotent) so the two views can never render simultaneously.
        self._enter_chat()
        chat = self.query_one("#chat", ScrollableContainer)
        msg = ChatMessage(role, content)
        msg.add_class("enter")
        chat.mount(msg)
        chat.scroll_end(animate=True)
        self.call_after_refresh(lambda: msg.remove_class("enter"))
        return msg

    def _scroll_chat(self) -> None:
        try:
            self.query_one("#chat", ScrollableContainer).scroll_end(animate=False)
        except Exception:  # noqa: BLE001
            pass

    def _prune_history(self) -> List[Dict[str, str]]:
        try:
            limit = int(__import__("os").getenv("CAPTURE_HELP_CONTEXT_MESSAGES", "30"))
        except ValueError:
            limit = 30
        return self.history if limit <= 0 else self.history[-limit:]

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
            save_session(self.sess_id, self.history)
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
    def _start_thinking(self) -> None:
        self._stop_thinking()
        chat = self.query_one("#chat", ScrollableContainer)
        self._thinking_row = ThinkingRow()
        chat.mount(self._thinking_row)
        self._thinking_dots = 0
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
        self._thinking_dots = (getattr(self, "_thinking_dots", 0) + 1) % 4
        dots = "." * self._thinking_dots
        if self._thinking_row is not None and self._thinking_row.label is not None:
            self._thinking_row.label.update(f"✦ Thinking{dots}")

    # ------------------------------------------------------------------ #
    # Streaming worker (runs in a background thread)
    # ------------------------------------------------------------------ #
    def _get_provider(self):
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
            self.call_from_thread(self._fallback_to_local)
            return OllamaProvider(model="gemma3:12b", base_url="http://localhost:11434/v1")
        return DeepSeekProvider(model=model)

    def _fallback_to_local(self) -> None:
        save_config(api_key="", provider="ollama", model="gemma3:12b", keep_key=True)
        self.notify("DeepSeek key missing/invalid — switched to local Gemma 3 (FREE).", severity="warning")
        self.footer.set_model("gemma3:12b")
        self._log_debug("[yellow]Fallback[/yellow] -> local Gemma 3 12B")

    @work(thread=True, exclusive=False, group="generate")
    def _generate(self, pruned: List[Dict[str, str]], system_prompt: str) -> None:
        try:
            provider = self._get_provider()
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self._on_error, f"Could not initialize provider: {e}")
            return

        turn = 0
        while turn <= MAX_TOOL_TURNS:
            try:
                gen = provider.stream_completion(pruned, system_prompt)
                reply = ""
                for chunk, stats in gen:
                    if chunk:
                        reply += chunk
                        self.call_from_thread(self._on_token, chunk)
                    if stats:
                        self.call_from_thread(self._on_stats, stats)
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

            outputs: List[str] = []
            for kind, payload in calls:
                out = self._execute_tool_blocking(kind, payload, reply)
                display = payload if not isinstance(payload, tuple) else payload[0]
                outputs.append(out)
                self.call_from_thread(self._on_tool_output, kind, display, out)

            self.call_from_thread(
                self.history.append,
                {"role": "user", "content": f"Tool Output:\n{chr(10).join(outputs)[:20_000]}"},
            )
            self._save_session_threadsafe()
            pruned = self._prune_history_threadsafe()
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
            self._current_message = self.add_message("assistant", "")
        self._ui_text += chunk
        # Streaming cursor: append a blinking block after whatever has streamed.
        cursor = "▍" if len(self._ui_text) % 2 else "▋"
        self._current_message.update_markdown(self._ui_text + cursor)
        self._scroll_chat()

    def _on_stats(self, stats) -> None:
        self.footer.set_stats(stats)
        if getattr(stats, "cache_hit_tokens", 0):
            self._log_debug(f"[dim]cache hit[/dim] {stats.cache_hit_tokens} tokens")

    def _on_turn_done(self, reply: str) -> None:
        self._stop_thinking()
        if self._current_message is not None:
            self._current_message = None
        self._ui_text = ""
        self.history.append({"role": "assistant", "content": reply})
        self._save_session()

    def _on_tool_output(self, kind: str, display, out: str) -> None:
        icon = {"run": "⚡", "read": "▤", "search": "⌕", "write": "✎", "mcp": "⇄"}.get(kind, "⚙")
        short = out if len(out) < 1200 else out[:1200] + "\n…"
        self.add_message("tool", f"{icon} {display}\n{short}")
        self._log_debug(f"[cyan]{icon} tool {kind}:[/cyan] {display}")
        if kind in ("read", "write"):
            self._track_open_file(str(display))

    def _on_generation_finished(self) -> None:
        self._stop_thinking()
        self._current_message = None
        self._ui_text = ""
        self.footer.set_state("ready")
        self._save_session()
        self._flush_provider_log()

    def _on_error(self, msg: str) -> None:
        self._stop_thinking()
        self._current_message = None
        self._ui_text = ""
        self.footer.set_state("error")
        self.add_message("error", msg)
        self._log_debug(f"[red]Error:[/red] {msg}")
        self._flush_provider_log()

    # -- thread-safe variants for state used from the worker -- #
    def _flush_provider_log_threadsafe(self) -> None:
        self.call_from_thread(self._flush_provider_log)

    def _save_session_threadsafe(self) -> None:
        self.call_from_thread(self._save_session)

    def _prune_history_threadsafe(self) -> List[Dict[str, str]]:
        return self.call_from_thread(self._prune_history)

    # ------------------------------------------------------------------ #
    # Input handling
    # ------------------------------------------------------------------ #
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "prompt-input":
            return
        popup = self._popup()
        if popup is not None and popup.is_visible():
            cmd = popup.selected()
            if cmd:
                event.input.value = cmd + " "
                event.input.cursor_position = len(event.input.value)
                popup.hide()
                event.input.focus()
                return
        text = event.value.strip()
        event.input.value = ""
        popup.hide()
        if not text:
            return
        if text.startswith("/") or text.lower() in ("help", "exit", "quit", "clear"):
            status = self._handle_slash(text)
            if status is not None:
                return
        self._send(text)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Keep the slash popup in sync as the user types."""
        if event.input.id != "prompt-input":
            return
        value = event.value
        popup = self._popup()
        if popup is None:
            return
        if value.startswith("/"):
            count = popup.show(value)
            if self.debug_panel is not None and self.debug_panel.visible:
                self._log_debug(f"[magenta]slash[/magenta] {value!r} -> {count} match(es)")
        else:
            popup.hide()

    def _popup(self) -> SlashPopup | None:
        try:
            return self.query_one("#slash-popup", SlashPopup)
        except Exception:  # noqa: BLE001
            return None

    def _send(self, text: str) -> None:
        if self._gen_worker is not None and self._gen_worker.is_running:
            self.notify("Still generating — wait for the current reply to finish.", severity="warning")
            return
        self._enter_chat()
        self.history.append({"role": "user", "content": text})
        self.add_message("user", text)
        self._save_session()
        self._current_message = None
        self._ui_text = ""
        self._start_thinking()
        self._gen_worker = self._generate(self._prune_history(), self._build_system_prompt())

    # ------------------------------------------------------------------ #
    # Landing screen interactions
    # ------------------------------------------------------------------ #
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "qa-primary":
            # The hero action: focus the input and let the user type a prompt.
            self.query_one("#prompt-input", ChatInput).focus()
            self.notify("Type your prompt below, or use / for commands.", severity="information")
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
            self.sess_id = str(uuid.uuid4())[:8]
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

    def action_clear_chat(self) -> None:
        self.history = []
        self.query_one("#chat", ScrollableContainer).remove_children()
        self._show_home()
        self.footer.set_stats(None)
        self.notify("Conversation cleared.")

    def action_new_chat(self) -> None:
        self._save_session()
        self.history = []
        self.sess_id = str(uuid.uuid4())[:8]
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
