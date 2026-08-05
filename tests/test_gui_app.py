"""Tests for the Textual glass chat UI and its fallbacks."""

import asyncio
import sys
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
            app._get_provider = lambda: FakeProvider()
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
            assert inp.placeholder == "What would you like to build today?"
            app.add_message("user", "hello")
            await pilot.pause(app._VIEW_FADE_S + 0.1)
            assert inp.placeholder == "Ask Capture Help…"
            app._handle_slash("/clear")
            await pilot.pause()
            assert inp.placeholder == "What would you like to build today?"

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