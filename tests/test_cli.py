import pytest
from typer.testing import CliRunner

from capture_help import __version__
from capture_help.cli import app

runner = CliRunner()

def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout

def test_doctor_command():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "System Doctor & Diagnostics" in result.stdout

def test_stats_command():
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "Token Analytics & Cost Savings" in result.stdout

def test_audit_command():
    result = runner.invoke(app, ["audit"])
    assert result.exit_code in [0, 1]
    assert "Security & Dependency Auditor" in result.stdout

def test_secrets_command():
    result = runner.invoke(app, ["secrets"])
    assert result.exit_code == 0
    assert "Hardcoded Secret Inspector" in result.stdout
