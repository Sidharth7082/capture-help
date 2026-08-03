import pytest
from typer.testing import CliRunner

from capture_help.cli import app

runner = CliRunner()

def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "2.1.0" in result.stdout

def test_doctor_command():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "System Doctor & Diagnostics" in result.stdout

def test_models_command():
    result = runner.invoke(app, ["models"])
    assert result.exit_code == 0
    assert "deepseek-v4-flash" in result.stdout

def test_tui_command():
    result = runner.invoke(app, ["tui"])
    assert result.exit_code == 0
    assert "TUI Dashboard" in result.stdout

def test_plugin_list_command():
    result = runner.invoke(app, ["plugin", "list"])
    assert result.exit_code == 0
    assert "qml-glassmorphism" in result.stdout
