from typer.testing import CliRunner
from capture_help.cli import app
from capture_help.memory import add_memory, get_all_memories, clear_memories
from capture_help.self_improve import get_user_profile, create_auto_skill, list_auto_skills

runner = CliRunner()

def test_neofetch_dashboard():
    result = runner.invoke(app, ["neofetch"])
    assert result.exit_code == 0
    assert "Arch Linux" in result.output or "Dashboard" in result.output

def test_memory_and_learn_commands():
    clear_memories()
    add_memory("test_cat", "Always use pacman for Arch Linux")
    memories = get_all_memories()
    assert len(memories) >= 1
    assert "pacman" in memories[0]["content"]

    result = runner.invoke(app, ["memory", "list"])
    assert result.exit_code == 0

def test_hermes_subcommands():
    result_distill = runner.invoke(app, ["hermes", "distill"])
    assert result_distill.exit_code == 0

    result_persona = runner.invoke(app, ["hermes", "persona"])
    assert result_persona.exit_code == 0

    result_recall = runner.invoke(app, ["hermes", "recall", "pacman"])
    assert result_recall.exit_code == 0

    result_daemon = runner.invoke(app, ["hermes", "daemon"])
    assert result_daemon.exit_code == 0

def test_table_command():
    json_sample = '[{"Name": "Pacman", "Type": "Package Manager"}]'
    result = runner.invoke(app, ["table", json_sample])
    assert result.exit_code == 0
    assert "Pacman" in result.output
