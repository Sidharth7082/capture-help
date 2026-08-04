from typer.testing import CliRunner
from capture_help.cli import app

runner = CliRunner()

def test_arch_subcommands():
    res_info = runner.invoke(app, ["arch", "info"])
    assert res_info.exit_code == 0

    res_clean = runner.invoke(app, ["arch", "clean"])
    assert res_clean.exit_code == 0

def test_gpu_command():
    res = runner.invoke(app, ["gpu"])
    assert res.exit_code == 0

def test_scan_command():
    res = runner.invoke(app, ["scan"])
    assert res.exit_code == 0

def test_redact_command():
    res = runner.invoke(app, ["redact", "sk-proj-12345678901234567890"])
    assert res.exit_code == 0
    assert "[REDACTED_API_KEY]" in res.output

def test_disk_command():
    res = runner.invoke(app, ["disk"])
    assert res.exit_code == 0

def test_firewall_command():
    res = runner.invoke(app, ["firewall"])
    assert res.exit_code == 0
