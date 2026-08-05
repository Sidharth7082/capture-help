"""Regression tests for bugs found during the capture-help audit."""

from typer.testing import CliRunner

from capture_help.cli import app

runner = CliRunner()


def test_key_command_saves_without_nameerror():
    """Bug: `capture-help key sk-...` crashed with NameError (save_config/console undefined)."""
    res = runner.invoke(app, ["key", "sk-regression-test-key-123456789"])
    assert res.exit_code == 0
    assert "Saved DeepSeek API key" in res.output
    assert "NameError" not in res.output


def test_changelog_command_imports_optional():
    """Bug: changelog_command used Optional without importing it (NameError at runtime)."""
    from capture_help.commands.changelog import changelog_command

    assert changelog_command is not None


def test_collect_directory_info_exists_and_runs(tmp_path):
    """Bug: review on a directory crashed because collect_directory_info was missing."""
    from capture_help.utils import collect_directory_info

    src = tmp_path / "proj"
    (src / "pkg").mkdir(parents=True)
    (src / "pkg" / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    info = collect_directory_info(src)
    assert info["total_files"] == 1
    assert info["primary_language"] == "Python"
    assert info["languages"] == {"Python": 1}
    assert len(info["files"]) == 1


def test_parse_tool_calls_pairs_each_write_with_its_code_block():
    """Bug: multiple TOOL_WRITE calls all wrote the same (last) code block."""
    from capture_help.gui.tools import parse_tool_calls

    text = (
        "Create two files.\n"
        "TOOL_WRITE: a.txt\n"
        "```text\n"
        "AAA content\n"
        "```\n"
        "TOOL_WRITE: b.txt\n"
        "```text\n"
        "BBB content\n"
        "```\n"
    )
    writes = [p for k, p in parse_tool_calls(text) if k == "write"]
    assert writes == [("a.txt", "AAA content"), ("b.txt", "BBB content")]


def test_provider_display_name_for_deepseek(monkeypatch):
    """Bug: cloud provider was labelled 'OpenCode Zen' instead of DeepSeek."""
    from capture_help.config import settings
    from capture_help.gui.widgets import provider_display_name

    monkeypatch.setenv("DEFAULT_PROVIDER", "deepseek")
    assert provider_display_name() == "DeepSeek"

    monkeypatch.setenv("DEFAULT_PROVIDER", "ollama")
    assert provider_display_name() == "Ollama (Local)"

    monkeypatch.setenv("DEFAULT_PROVIDER", "openrouter")
    assert provider_display_name() == "Openrouter"


def test_review_directory_path_resolves(tmp_path, monkeypatch, capsys):
    """End-to-end: `review <dir>` must not crash on the directory code path."""
    import capture_help.commands.review as review_mod

    src = tmp_path / "proj"
    src.mkdir()
    (src / "mod.py").write_text("x = 1\n", encoding="utf-8")

    captured = {}

    class FakeProvider:
        def stream_completion(self, messages, system_prompt=None, temperature=0.7):
            yield "## Review\n\nLooks fine.", None

    monkeypatch.setattr(review_mod, "get_provider", lambda *a, **k: FakeProvider())
    monkeypatch.setattr(review_mod.sys.stdin, "isatty", lambda: True)

    review_mod.review_command(str(src))
    out = capsys.readouterr().out
    assert "Reviewing" in out
    assert "Traceback" not in out
