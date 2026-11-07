"""Tests for the Textual glass chat UI and its fallbacks."""

import asyncio
import sys
import threading
from types import SimpleNamespace

import pytest

from capture_help.deepseek import TokenUsageStats
from capture_help.gui.app import CaptureHelpApp


class FakeProvider:
    """Minimal streaming provider for UI tests (no network)."""

    def stream_completion(self, messages, system_prompt=None, temperature=0.7):
        for piece in ("Hello ", "**world**."):
            yield piece, None
        yield "", TokenUsageStats(
            duration_seconds=1.2,
            prompt_tokens=10,
            completion_tokens=8,
            total_tokens=18,
            cost_usd=0.0,
            model="fake-model",
        )


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Keep tests from writing to the real ~/.config/capture-help."""
    monkeypatch.setenv("CAPTURE_HELP_CONFIG_DIR", str(tmp_path / "config"))
    import capture_help.config
    import capture_help.history
    import capture_help.memory
    import capture_help.self_improve

    monkeypatch.setattr(capture_help.history, "HISTORY_DIR", tmp_path / "history")
    monkeypatch.setattr(capture_help.config, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(capture_help.config, "CONFIG_FILE", tmp_path / "config" / ".env")
    monkeypatch.setattr(capture_help.self_improve, "PROFILE_PATH", tmp_path / "user_profile.json")
    monkeypatch.setattr(capture_help.self_improve, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(capture_help.memory, "MEMORY_DB_PATH", tmp_path / "memory.db")


def test_app_composes_and_renders():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.add_message("user", "Hello")
            await pilot.pause()
            app.add_message("assistant", "**Hi!**")
            await pilot.pause()
            app.add_message("error", "boom")
            await pilot.pause()
            chat = app.query_one("#chat")
            assert chat.children

    asyncio.run(scenario())


def test_streaming_updates_history_and_footer():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            app._get_provider = lambda notify_fallback=True: FakeProvider()
            app._send("Say hello")
            for _ in range(100):
                if app._gen_worker is not None and app._gen_worker.is_finished:
                    break
                await pilot.pause(0.05)
            await pilot.pause()
            assert app.history[-1]["role"] == "assistant"
            assert "Hello" in app.history[-1]["content"]
            assert app.footer.tokens_label is not None

    asyncio.run(scenario())


def test_slash_help_and_debug_toggle():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app._handle_slash("/help") is True
            await pilot.pause()
            app.action_toggle_debug()
            await pilot.pause()
            panel = app.query_one("#debug-panel")
            assert panel.styles.display == "block"
            app.action_toggle_debug()
            await pilot.pause()
            assert panel.styles.display == "none"

    asyncio.run(scenario())


def test_model_picker_screen_mounts():
    from capture_help.gui.modals import ModelPickerScreen
    from capture_help.deepseek import DEEPSEEK_MODELS

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(ModelPickerScreen(DEEPSEEK_MODELS, current="gemma3:12b"))
            await pilot.pause()
            assert app.screen is not None

    asyncio.run(scenario())


def test_slash_model_with_arg_switches_config():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            ok = app._handle_slash("/model gemma3:12b")
            assert ok is True
            from capture_help.config import settings

            assert settings.default_provider == "ollama"

    asyncio.run(scenario())


def test_chat_command_non_tty_fallback(monkeypatch, capsys):
    from capture_help.commands.chat import chat_command

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    chat_command()
    out = capsys.readouterr().out
    assert "AI Assistant Chat" in out


def test_tui_command_non_tty_fallback(monkeypatch, capsys):
    from capture_help.commands.tui import tui_command

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    tui_command()
    out = capsys.readouterr().out
    assert "Project Files" in out
    assert "Quick Commands" in out


def test_landing_screen_shows_on_empty_state_and_hides_on_send():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            landing = app.query_one("#landing")
            assert landing.styles.display == "block"
            app._send("hello")
            await pilot.pause(app._VIEW_FADE_S + 0.1)
            assert app.query_one("#landing").styles.display == "none"
            assert app.query_one("#chat").styles.display != "none"

    asyncio.run(scenario())


def test_landing_chip_fills_input():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.query_one("#chip-1").press()
            await pilot.pause()
            assert app.query_one("#prompt-input").value == "Fix build errors..."

    asyncio.run(scenario())


def test_home_and_chat_views_are_mutually_exclusive_after_fade():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            landing = app.query_one("#landing")
            chat = app.query_one("#chat")
            assert landing.styles.display == "block"
            assert chat.styles.height.value == 0
            app._send("hello")
            await pilot.pause(app._VIEW_FADE_S + 0.1)
            assert landing.styles.display == "none"
            assert landing.styles.height.value == 0
            assert str(chat.styles.height) == "1fr"
            app._handle_slash("/clear")
            await pilot.pause()
            assert app.query_one("#landing").styles.display == "block"
            assert app.query_one("#chat").styles.height.value == 0

    asyncio.run(scenario())


def test_any_message_transitions_home_to_chat():
    """A message landing via add_message (not just _send) must leave Home —
    covers slash commands, quick actions and persona greetings that append a
    message directly without a full _send."""
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            assert app.query_one("#landing").styles.display == "block"
            assert app.query_one("#chat").styles.height.value == 0
            app.add_message("user", "hi")
            await pilot.pause(app._VIEW_FADE_S + 0.1)
            assert app.query_one("#landing").styles.display == "none"
            assert str(app.query_one("#chat").styles.height) == "1fr"

    asyncio.run(scenario())


def test_slash_read_transitions_home_to_chat():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app._handle_slash("/read capture_help/__init__.py")
            await pilot.pause(app._VIEW_FADE_S + 0.1)
            assert app.query_one("#landing").styles.display == "none"
            assert app.history

    asyncio.run(scenario())


def test_input_placeholder_follows_view_state():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            inp = app.query_one("#prompt-input")
            assert inp.placeholder == "Explain code, fix bugs, or search your workspace…"
            app.add_message("user", "hello")
            await pilot.pause(app._VIEW_FADE_S + 0.1)
            assert inp.placeholder == "Ask Capture Help…"
            app._handle_slash("/clear")
            await pilot.pause()
            assert inp.placeholder == "Explain code, fix bugs, or search your workspace…"

    asyncio.run(scenario())


def test_background_layers_sit_below_the_ui():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            layers = app.screen.layers
            for name in ("wallpaper", "overlay", "ui"):
                assert name in layers
            # wallpaper and dark-overlay must render beneath the glass chrome
            wallpaper = app.query_one("#wallpaper")
            overlay = app.query_one("#dark-overlay")
            assert layers.index(wallpaper.layer) < layers.index("ui")
            assert layers.index(overlay.layer) < layers.index("ui")
            # the full-bleed backgrounds cover the entire terminal screen
            assert wallpaper.region == app.screen.region

    asyncio.run(scenario())


def test_landing_quick_action_attaches_diff(monkeypatch):
    from capture_help import gui
    from capture_help.gui import app as gui_app

    monkeypatch.setattr(gui_app, "get_git_diff", lambda: "+def foo():\n    pass\n")

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.query_one("#qa-git").press()
            await pilot.pause()
            assert app.history[-1]["role"] == "user"
            assert "def foo()" in app.history[-1]["content"]

    asyncio.run(scenario())


def test_parse_tool_calls():
    from capture_help.gui.tools import parse_tool_calls

    text = (
        "Let me read a file.\n"
        "TOOL_READ: src/main.py\n"
        "Then search.\n"
        "TOOL_SEARCH: glass effect\n"
        "And run.\n"
        "TOOL_RUN: ls -la\n"
    )
    kinds = [c[0] for c in parse_tool_calls(text)]
    assert sorted(kinds) == ["read", "run", "search"]


# --------------------------------------------------------------------------- #
# Slash-command popup
# --------------------------------------------------------------------------- #
def test_slash_popup_appears_on_slash_and_filters():
    from capture_help.gui.widgets import SlashPopup

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            popup = app.query_one("#slash-popup", SlashPopup)
            assert popup.styles.display == "none"
            app.query_one("#prompt-input").value = "/"
            await pilot.pause()
            assert popup.styles.display != "none"
            assert popup.option_list.option_count > 0
            app.query_one("#prompt-input").value = "/model"
            await pilot.pause()
            assert popup.option_list.option_count >= 1
            ids = {o.id for o in popup.option_list.options}
            assert "/model" in ids
            app.query_one("#prompt-input").value = "hello"
            await pilot.pause()
            assert popup.styles.display == "none"

    asyncio.run(scenario())


def test_slash_popup_arrow_navigation_and_tab_fill():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            inp = app.query_one("#prompt-input")
            inp.value = "/model"
            await pilot.pause()
            popup = app.query_one("#slash-popup")
            assert popup.styles.display != "none"
            inp.focus()
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("tab")
            await pilot.pause()
            assert inp.value.startswith("/")
            assert inp.value.endswith(" ")

    asyncio.run(scenario())


def test_ctrl_shift_m_and_ctrl_p_open_pickers():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.action_open_model_picker()
            await pilot.pause()
            assert app.screen is not None
            app.screen.dismiss(None)
            await pilot.pause()
            app.action_open_persona_picker()
            await pilot.pause()
            assert app.screen is not None

    asyncio.run(scenario())


def test_footer_model_click_opens_picker():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            captured = []

            def fake_action():
                captured.append(True)

            app.action_open_model_picker = fake_action
            footer = app.footer
            footer.on_click(SimpleNamespace(widget=footer.model_label))
            await pilot.pause()
            assert captured == [True]

    asyncio.run(scenario())


def test_slash_code_command_moves_highlight_and_escape_hides():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            inp = app.query_one("#prompt-input")
            inp.value = "/"
            await pilot.pause()
            popup = app.query_one("#slash-popup")
            assert popup.styles.display != "none"
            inp.focus()
            before = popup.selected()
            popup.move(1)
            after = popup.selected()
            assert after is not None and after != before
            await pilot.press("escape")
            await pilot.pause()
            assert popup.styles.display == "none"

    asyncio.run(scenario())

# --------------------------------------------------------------------------- #
# UX polish: Today's Workspace, primary button, model badge, relatives
# --------------------------------------------------------------------------- #
def test_landing_has_primary_ask_button_and_no_duplicate_recent_list():
    """The landing panel exposes a primary 'Ask Capture Help' CTA and the
    duplicated Recent Conversations panel has been replaced by Workspace."""
    from capture_help.gui.widgets import LandingPanel

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            primary = app.query_one("#qa-primary")
            assert "qa-primary" in primary.classes
            landing = app.query_one("#landing", LandingPanel)
            # Recent conversations now live only in the sidebar
            assert len(landing.query("#landing-recent")) == 0
            assert app.query_one("#recent-chats") is not None
            # Workspace summary populated
            assert app.query_one("#workspace-items").children

    asyncio.run(scenario())


def test_primary_button_focuses_input(monkeypatch):
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            inp = app.query_one("#prompt-input")
            inp.blur()
            await pilot.pause()
            app.query_one("#qa-primary").press()
            await pilot.pause()
            assert app.focused is inp

    asyncio.run(scenario())


def test_workspace_summary_and_header_strip(monkeypatch):
    from capture_help.gui import widgets as w

    monkeypatch.setattr(
        w,
        "workspace_summary",
        lambda project: {"modified": 3, "last_commit": "abc Improve renderer",
                         "todos": 12, "clean": True},
    )

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            # Header uses a compact strip, not wide per-field cards
            assert app.query_one("#workspace-strip") is not None
            assert len(app.query(".workspace-grid")) == 0
            # Footer / model label is a badge
            footer = app.footer
            assert "model-local" in footer.model_label.classes or "model-cloud" in footer.model_label.classes

    asyncio.run(scenario())


def test_relative_time_and_title_emoji():
    import time

    from capture_help.gui.widgets import relative_time, title_emoji

    assert "min ago" in relative_time(time.time() - 120)
    assert "just now" in relative_time(time.time() - 5)
    assert title_emoji("Fix the QML crash") == "🐛"
    assert title_emoji("Refactor render pipeline") == "🔧"
    assert title_emoji("Some random thing") == "💬"


def test_sidebar_recent_chats_are_enriched(monkeypatch):
    import time
    from capture_help.gui.widgets import SidebarPanel

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            sidebar = app.query_one("#sidebar", SidebarPanel)
            sessions = [
                {"id": "1", "title": "Fix build error", "turns": 3, "timestamp": time.time() - 120},
                {"id": "2", "title": "Add feature", "turns": 1, "timestamp": time.time()},
            ]
            sidebar.set_recent_chats(sessions, active_id="2")
            await pilot.pause()
            opts = list(sidebar.recent_list.options)
            assert len(opts) == 2
            assert "🐛" in str(opts[0].prompt)
            assert "min ago" in str(opts[0].prompt)
            # the active conversation is marked with ▌ and bold cyan
            active = str(opts[1].prompt)
            assert "▌" in active
            from rich.text import Text as RichText

            assert isinstance(opts[1].prompt, RichText)
            assert "bold" in str(opts[1].prompt.style) or "bold" in str(
                next(iter(opts[1].prompt.spans), None)
            )
            assert "▌" not in str(opts[0].prompt)

    asyncio.run(scenario())


def test_sidebar_navigation_starts_chat_and_opens_search():
    from capture_help.gui.modals import SearchModal

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert "Capture Help" in str(app.query_one(".sidebar-brand-title").render())
            previous_session = app.sess_id
            app.query_one("#sidebar-new-chat").press()
            await pilot.pause()
            assert app.sess_id != previous_session
            assert app._in_home_view

            app.query_one("#sidebar-search").press()
            await pilot.pause()
            assert isinstance(app.screen, SearchModal)

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# Chat UX: role identity, full-width bubbles, sublayers, thinking, code cards
# --------------------------------------------------------------------------- #
def test_chat_message_has_role_label_and_avatar():
    from capture_help.gui.widgets import ROLE_AVATARS, ROLE_LABELS

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.add_message("user", "hello there")
            app.add_message("assistant", "**hi**")
            app.add_message("tool", "output", sublabel="🐚 Terminal")
            await pilot.pause()
            for role, label in (("user", "You"), ("assistant", "Capture Help"),
                                ("tool", "Tool")):
                set_of_role = app.query(f".role-{role}")
                assert set_of_role, f"no .role-{role}"
                msg = set_of_role[0]
                assert msg.query_one(".msg-role") is not None
            user_msg = app.query(".role-user")[0]
            assert "You" in str(user_msg.query_one(".msg-role").render())
            asst = app.query(".role-assistant")[0]
            assert "Capture Help" in str(asst.query_one(".msg-role").render())

    asyncio.run(scenario())


def test_tool_message_carries_terminal_sublabel():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.add_message("tool", "x", sublabel="🐚 Terminal")
            await pilot.pause()
            tool_msg = app.query(".role-tool")[0]
            assert "🐚" in str(tool_msg.query_one(".msg-role").render())

    asyncio.run(scenario())


def test_code_fence_renders_language_and_line_numbers(monkeypatch):
    """Assistant markdown code fences become numbered, labelled cards."""
    from capture_help.gui.widgets import CodeMarkdown

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.add_message("assistant", "```python\nprint('x')\nprint('y')\n```")
            await pilot.pause()
            from capture_help.gui.widgets import CodeFence

            fences = app.query(CodeFence)
            assert len(fences) >= 1, "no CodeFence rendered"
            fence = fences[0]
            assert fence.query_one(".code-lang") is not None
            content = str(fence._content_label.render())
            assert "1" in content and "2" in content  # line numbers present
            assert "print" in content


def test_thinking_row_shows_stage_and_progress():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._start_thinking()
            await pilot.pause(0.5)
            row = app.query_one("#thinking-row")
            assert row.stage_label is not None
            assert row.progress_label is not None
            assert str(row.progress_label.render()).startswith("▰")
            app._stop_thinking()
            await pilot.pause()

    asyncio.run(scenario())


def test_workspace_summary_includes_branch(monkeypatch):
    from capture_help.gui import widgets as w

    monkeypatch.setattr(
        w, "workspace_summary",
        lambda p: {"modified": 8, "last_commit": "abc x", "todos": 770,
                   "clean": True, "branch": "main"},
    )

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            items = app.query_one("#workspace-items")
            rows_text = " ".join(
                str(lbl.render()) for row in items.children for lbl in row.children
            )
            assert "Branch" in rows_text
            assert "main" in rows_text

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# Code-block actions: Copy / Insert buttons
# --------------------------------------------------------------------------- #
def test_code_fence_has_copy_and_insert_buttons():
    """Code fences expose Copy (to clipboard) and Insert (into input) actions."""
    from capture_help.gui.widgets import CodeFence

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.add_message("assistant", "```python\nprint('x')\n```")
            await pilot.pause()
            fence = app.query(CodeFence)[0]
            assert fence.copy_btn is not None
            assert fence.insert_btn is not None
            fence.copy_btn.press()
            await pilot.pause()
            assert app._clipboard == "print('x')"
            fence.insert_btn.press()
            await pilot.pause()
            assert app.query_one("#prompt-input").value == "print('x')"

    asyncio.run(scenario())


def test_diff_fence_renders_as_diff_card():
    """A ```diff fence becomes a distinct card: filename header, +/- colours,
    Copy action only (no Insert)."""
    from capture_help.gui.widgets import CodeFence

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.add_message(
                "assistant",
                "```diff\n"
                "--- a/Renderer.cpp\n"
                "+++ b/Renderer.cpp\n"
                "@@ -1,2 +1,2 @@\n"
                "-old\n"
                "+new\n"
                "```",
            )
            await pilot.pause()
            fence = app.query(CodeFence)[0]
            assert fence._is_diff()
            assert fence.query_one(".diff-card") is not None
            assert "Renderer.cpp" in str(fence.query_one(".code-lang").render())
            assert fence.copy_btn is not None
            assert getattr(fence, "insert_btn", None) is None
            styles = {str(s.style) for s in fence._content_label.content._spans}
            assert "#f2556f" in styles  # removal
            assert "#4ed98c" in styles  # addition
            assert "bold #6aa9f0" in styles  # hunk
            assert fence._content_label.content._text == (
                "1 --- a/Renderer.cpp\n"
                "2 +++ b/Renderer.cpp\n"
                "3 @@ -1,2 +1,2 @@\n"
                "4 -old\n"
                "5 +new"
            )

    asyncio.run(scenario())


def test_diff_helpers_unit():
    from capture_help.gui.widgets import diff_line_style, looks_like_diff

    assert looks_like_diff("diff --git a/x b/x\n-old\n+new")
    assert looks_like_diff("--- a/x\n+++ b/x\n-old\n+new")
    assert not looks_like_diff("hello\n- not a diff\n+ 2 + 2 = 4")
    assert looks_like_diff("") is False
    assert diff_line_style("+new") == "#4ed98c"
    assert diff_line_style("-old") == "#f2556f"
    assert diff_line_style("@@ -1 +1 @@") == "bold #6aa9f0"
    assert diff_line_style("+++ b/x") == "bold #8f9aa9"
    assert diff_line_style("context") == "#5d6878"


def test_tool_message_with_diff_content_uses_diff_colours():
    from rich.text import Text as RichText
    from textual.widgets import Static

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.add_message(
                "tool",
                "⎇ Git diff (4 lines)\n\ndiff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new",
            )
            await pilot.pause()
            tool_msg = app.query(".role-tool")[-1]
            statics = list(tool_msg.query(".bubble Static"))
            assert len(statics) == 1
            assert isinstance(statics[0].content, RichText)
            styles = {str(s.style) for s in statics[0].content.spans}
            assert "#4ed98c" in styles and "#f2556f" in styles
            # Plain (non-diff) tool messages stay unstyled strings
            app.add_message("tool", "⚡ ls\n\nfile1\nfile2")
            await pilot.pause()
            plain = app.query(".role-tool")[-1].query(".bubble Static")[0]
            assert isinstance(plain.content, str)

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# AI-generated conversation titles
# --------------------------------------------------------------------------- #
def test_ai_generated_conversation_title():
    """After the first reply, a background worker refines the session title
    and the sidebar/session pick it up."""
    from capture_help.history import list_sessions

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            app._get_provider = lambda notify_fallback=True: FakeProvider()
            app._send("Say hello")
            for _ in range(200):
                if app._ai_title:
                    break
                await pilot.pause(0.05)
            assert app._ai_title, "AI title was never applied"
            assert "Hello" in app._ai_title
            assert app._title_requested is True
            saved = list_sessions()
            assert saved and saved[0]["id"] == app.sess_id
            assert saved[0]["title"] == app._ai_title

    asyncio.run(scenario())


def test_sanitize_title():
    from capture_help.gui.app import CaptureHelpApp

    assert CaptureHelpApp._sanitize_title('"Fix the build"') == "Fix the build"
    assert CaptureHelpApp._sanitize_title("Title: Improve renderer.") == "Improve renderer"
    assert CaptureHelpApp._sanitize_title("  Weather report: sunny ") == "Weather report: sunny"
    assert CaptureHelpApp._sanitize_title("   ") == ""


def test_title_provider_lookup_skips_fallback_side_effects(monkeypatch):
    """The title worker builds its provider without re-notifying the missing-
    key fallback (the generation worker already handled that)."""
    monkeypatch.setenv("DEFAULT_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "invalid-test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    from capture_help.gui.app import CaptureHelpApp

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            calls = []
            app._fallback_to_local = lambda: calls.append(True)
            provider = app._get_provider(notify_fallback=False)
            assert provider is not None
            assert calls == []  # no fallback notification fired
            # The default path notifies, but only from a worker thread
            # (call_from_thread is illegal on the app's own thread).
            errs = []

            def call_default():
                try:
                    app._get_provider()
                except Exception as e:  # noqa: BLE001
                    errs.append(e)

            t = threading.Thread(target=call_default)
            t.start()
            t.join(timeout=5)
            assert errs == []
            await pilot.pause()
            assert calls == [True]

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# UX polish: tighter user bubbles, live context, ✓ thinking stages
# --------------------------------------------------------------------------- #
def test_user_bubble_stays_compact():
    """User bubbles auto-size tightly — one line in, one line out."""
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.add_message("user", "hello")
            await pilot.pause()
            bubble = app.query(".role-user")[0].query_one(".bubble")
            assert bubble.size.height <= 2
            # multi-paragraph messages don't gain the default 1-row gaps
            # (with the margin-zero rule: 2 rows; without it: 4 — so <= 3
            # guards against the rule silently disappearing)
            app.add_message("user", "one\n\ntwo")
            await pilot.pause()
            bubble = app.query(".role-user")[-1].query_one(".bubble")
            assert bubble.size.height <= 3

    asyncio.run(scenario())


def test_thinking_row_fixed_stage_and_done_lines():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._start_thinking("Running tools…")
            await pilot.pause(0.3)
            row = app.query_one("#thinking-row")
            assert "Running tools…" in str(row.stage_label.render())
            assert row._stage_fixed
            row.add_done("Searched glass")
            await pilot.pause()
            done = [str(l.render()) for l in row.query(".thinking-done")]
            assert done == ["✓ Searched glass"]
            app._stop_thinking()
            await pilot.pause()

    asyncio.run(scenario())


def test_tool_output_appends_done_line():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # no pause between start and outputs: done lines may arrive while
            # the thinking row's container is still being attached — they must
            # queue and flush without error or loss
            app._start_thinking("Running tools…")
            app._on_tool_output("search", "glass effect", "Found 2 matches\nrenderer.cpp")
            app._on_tool_output("run", "cargo build", "Action cancelled by user.")
            await pilot.pause()
            row = app.query_one("#thinking-row")
            done = [str(l.render()) for l in row.query(".thinking-done")]
            assert "✓ Searched glass effect" in done
            assert "✕ cargo build (cancelled)" in done
            assert "✓ cargo build" not in done
            app._stop_thinking()

    asyncio.run(scenario())


def test_live_context_usage_in_footer():
    from capture_help.deepseek import TokenUsageStats

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._on_stats(TokenUsageStats(
                duration_seconds=1.0, prompt_tokens=2300, completion_tokens=120,
                total_tokens=2420, cost_usd=0.0, model="m"))
            await pilot.pause()
            assert "2.3k / 32k" in str(app.footer.context_label.render())
            app._on_stats(TokenUsageStats(
                duration_seconds=1.0, prompt_tokens=320, completion_tokens=5,
                total_tokens=325, cost_usd=0.0, model="m"))
            await pilot.pause()
            assert "320 / 32k" in str(app.footer.context_label.render())

    asyncio.run(scenario())


def test_fmt_k():
    from capture_help.gui.app import CaptureHelpApp

    assert CaptureHelpApp._fmt_k(320) == "320"
    assert CaptureHelpApp._fmt_k(2300) == "2.3k"
    assert CaptureHelpApp._fmt_k(0) == "0"
    assert CaptureHelpApp._fmt_k(32000) == "32k"
    assert CaptureHelpApp._fmt_k(32768) == "32.8k"


# --------------------------------------------------------------------------- #
# Sidebar: active highlight + click-to-load, header project line
# --------------------------------------------------------------------------- #
def test_load_session_from_sidebar():
    """Selecting a recent conversation loads it into the chat view."""
    import time

    from capture_help.history import save_session

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            save_session(
                "abc123",
                [
                    {"role": "user", "content": "Fix the renderer"},
                    {"role": "assistant", "content": "Done."},
                ],
                title="Fix the renderer",
            )
            app._load_session("abc123")
            await pilot.pause()
            assert app.sess_id == "abc123"
            assert app.history[-1]["role"] == "assistant"
            assert app._ai_title == "Fix the renderer"
            assert app._title_requested is True  # no AI re-title of loaded session
            assert len(app.query(".chat-message")) >= 2

    asyncio.run(scenario())


def test_sidebar_click_event_loads_session():
    """The OptionSelected handler (fired by a real click) routes to _load_session."""
    from types import SimpleNamespace

    from capture_help.history import save_session

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            save_session("sid9", [{"role": "user", "content": "hello"}], title="hello")
            app.on_option_list_option_selected(
                SimpleNamespace(option=SimpleNamespace(id="session:sid9"))
            )
            await pilot.pause()
            assert app.sess_id == "sid9"
            assert any(m["content"] == "hello" for m in app.history)

    asyncio.run(scenario())


def test_load_session_ignored_while_generating():
    """Loading a session mid-generation is refused (no history clobbering)."""
    from types import SimpleNamespace

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            original = app.sess_id
            original_history = list(app.history)
            app._gen_worker = SimpleNamespace(is_running=True)
            app._load_session("other-session")
            await pilot.pause()
            assert app.sess_id == original
            assert app.history == original_history  # history untouched
            app._gen_worker = None

    asyncio.run(scenario())


def test_primary_cta_has_no_floating_toast():
    """The primary CTA focuses the input without a detached helper toast."""
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            inp = app.query_one("#prompt-input")
            inp.blur()
            await pilot.pause()
            app.query_one("#qa-primary").press()
            await pilot.pause()
            assert app.focused is inp

    asyncio.run(scenario())


def test_header_has_prominent_project_line():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.query_one("#app-header")
            assert header.query_one("#project-name") is not None
            assert header.query_one("#strip-langs") is not None
            assert header.query_one("#workspace-strip") is not None
            assert "Capture Help" in str(header.query_one("#app-title").render())
            # project name rendered from fingerprint
            assert "capture-help" in str(header.query_one("#project-name").render())

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# Phase 1 features: dashboard stats, project memory, context viewer, palette
# --------------------------------------------------------------------------- #
def test_workspace_summary_counts_dependencies_and_tests(tmp_path):
    from capture_help.gui.widgets import workspace_summary

    (tmp_path / "pyproject.toml").write_text(
        'dependencies = [\n'
        '    "typer>=0.12.0",\n'
        '    "rich>=13.7.0",\n'
        ']\n'
        '[project.optional-dependencies]\n'
        'dev = ["pytest>=7.0.0"]\n'
    )
    (tmp_path / "requirements-dev.txt").write_text("requests==2.31\nflask==3.0\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_render.py").write_text(
        "def test_render():\n    pass\n\ndef test_blur():\n    pass\n"
    )
    s = workspace_summary({"root": str(tmp_path)})
    assert s["deps"] == 5  # 2 + 1 pyproject, 2 requirements
    assert s["tests"] == 2


def test_project_memory_panel_shows_learned_rules():
    from capture_help.memory import add_memory, get_all_memories

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            add_memory("user_preference", "Use 4-space indentation")
            app._populate_sidebar()
            await pilot.pause()
            panel = app.query_one("#memory-list")
            texts = " ".join(str(l.render()) for l in panel.children)
            assert "✓ Use 4-space indentation" in texts
            # empty/whitespace content must not crash the panel renderer
            app.sidebar.set_memories([{"content": "   "}, {"content": ""}])
            await pilot.pause()
            texts = " ".join(str(l.render()) for l in panel.children)
            assert "✓ (empty)" in texts

    asyncio.run(scenario())


def test_context_viewer_shows_files_and_usage():
    from textual.widgets import Static

    from capture_help.deepseek import TokenUsageStats

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._open_files = ["Renderer.cpp", "Workspace.qml"]
            app._on_stats(TokenUsageStats(
                duration_seconds=1.0, prompt_tokens=2300, completion_tokens=100,
                total_tokens=2400, cost_usd=0.0, model="m"))
            app.action_open_context()
            await pilot.pause()
            await pilot.pause()
            from capture_help.gui.modals import ContextViewerScreen

            assert isinstance(app.screen, ContextViewerScreen)
            modal = app.screen
            text = " ".join(str(w.render()) for w in modal.query(Static))
            assert "Renderer.cpp" in text and "Workspace.qml" in text
            assert "2,300 / 32,000" in text
            modal.dismiss(None)
            await pilot.pause()

    asyncio.run(scenario())


def test_command_palette_enabled_and_bindings():
    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.ENABLE_COMMAND_PALETTE is True
            assert app.COMMAND_PALETTE_BINDING == "ctrl+shift+p"
            assert app.COMMANDS  # providers registered
            from capture_help.gui.app import CaptureHelpCommands

            assert CaptureHelpCommands in app.COMMANDS
            # ctrl+shift+p opens the palette
            await pilot.press("ctrl+shift+p")
            await pilot.pause()
            from textual.command import CommandPalette

            assert isinstance(app.screen, CommandPalette)
            app.screen.dismiss()
            await pilot.pause()
            # ctrl+p still opens the persona picker (not the palette)
            app.action_open_persona_picker()
            await pilot.pause()
            await pilot.pause()
            from capture_help.gui.modals import PersonaPickerScreen

            assert isinstance(app.screen, PersonaPickerScreen)

    asyncio.run(scenario())


def test_command_palette_provider_lists_app_commands():
    from capture_help.gui.app import CaptureHelpCommands

    async def scenario():
        app = CaptureHelpApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            provider = CaptureHelpCommands(app.screen)
            hits = [h async for h in provider.discover()]
            prompts = [str(h.match_display) for h in hits]
            assert "New chat" in prompts
            assert "Open context viewer" in prompts
            assert "Save and quit" in prompts
            # search filters
            found = [h async for h in provider.search("context")]
            assert any("context" in str(h.match_display).lower() for h in found)

    asyncio.run(scenario())
