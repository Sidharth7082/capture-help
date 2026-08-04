import sys
from pathlib import Path
from typer.testing import CliRunner

from capture_help.cli import app
from capture_help.commands.summarize import collect_summary_input

runner = CliRunner()


def _file_input_args(tmp_path, name="sample.py"):
    f = tmp_path / name
    f.write_text("def add(a, b):\n    return a + b\n")
    return str(f)


def test_summarize_help():
    res = runner.invoke(app, ["summarize", "--help"])
    assert res.exit_code == 0
    assert "summarize" in res.output


def test_collect_from_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", type("Stdin", (), {"isatty": lambda self: True})())
    kind, content, label = collect_summary_input(_file_input_args(tmp_path), None)
    assert kind == "file"
    assert "def add" in content
    assert Path(label).name == "sample.py"


def test_collect_from_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", type("Stdin", (), {"isatty": lambda self: True})())
    (tmp_path / "lib.py").write_text("x = 1\n")
    (tmp_path / ".git").mkdir()
    kind, content, label = collect_summary_input(str(tmp_path), None)
    assert kind == "directory"
    assert "Project:" in content
    assert "lib.py" in content


def test_collect_empty_no_target(tmp_path, monkeypatch):
    class FakeStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", FakeStdin())
    monkeypatch.chdir(tmp_path)
    kind, content, label = collect_summary_input(None, None)
    assert kind == "" and content == ""


class FakeProvider:
    def stream_completion(self, messages, temperature=0.7):
        yield "## Summary\n\n**Local model output.**", None


def test_summarize_local_flag_routes_to_local(tmp_path, monkeypatch):
    import capture_help.commands.summarize as mod

    monkeypatch.setattr(mod, "_resolve_provider", lambda local, model: FakeProvider())
    f = tmp_path / "x.py"
    f.write_text("x = 1\n")
    res = runner.invoke(app, ["summarize", str(f), "--local", "--model", "qwen2.5-coder"])
    assert res.exit_code == 0
    assert "Local model output." in res.output


def test_summarize_model_flag_passed(tmp_path, monkeypatch):
    import capture_help.commands.summarize as mod

    captured = {}

    def fake_resolve(local, model):
        captured["model"] = model
        return FakeProvider()

    monkeypatch.setattr(mod, "_resolve_provider", fake_resolve)
    f = tmp_path / "y.py"
    f.write_text("y = 2\n")
    runner.invoke(app, ["summarize", str(f), "--model", "deepseek-chat"])
    assert captured["model"] == "deepseek-chat"
