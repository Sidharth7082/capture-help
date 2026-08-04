import os
import json
import pytest
from typer.testing import CliRunner
from capture_help.cli import app
from capture_help.config import settings, save_config
from capture_help.memory import add_memory, get_all_memories, clear_memories, init_memory_db
from capture_help.self_improve import get_user_profile, update_user_profile, create_auto_skill, list_auto_skills
from capture_help.cache import get_cached_system_prompt
from capture_help.commands.redact import redact_command
from capture_help.commands.neofetch import neofetch_command

runner = CliRunner()

# ----------------------------------------------------
# 1-15: Configuration & Provider Tests
# ----------------------------------------------------
def test_001_settings_obj():
    assert settings.deepseek_base_url is not None

def test_002_save_config_ollama_provider():
    save_config(api_key="test_key", provider="ollama", model="gemma3:12b")
    assert settings.default_provider == "ollama"

def test_003_save_config_deepseek_provider():
    save_config(api_key="test_key_ds", provider="deepseek", model="deepseek-v4-flash")
    assert settings.default_provider == "deepseek"

def test_004_config_deepseek_api_key():
    save_config(api_key="test_key_123")
    assert settings.deepseek_api_key == "test_key_123"

def test_005_config_defaults():
    save_config(api_key="test_key", provider="ollama")
    assert settings.default_provider == "ollama"

def test_006_cli_version():
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert "version" in res.output.lower() or "3." in res.output

def test_007_cli_help():
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "capture-help" in res.output

def test_008_doctor_help():
    res = runner.invoke(app, ["doctor", "--help"])
    assert res.exit_code == 0

def test_009_stats_help():
    res = runner.invoke(app, ["stats", "--help"])
    assert res.exit_code == 0

def test_010_audit_help():
    res = runner.invoke(app, ["audit", "--help"])
    assert res.exit_code == 0

def test_011_secrets_help():
    res = runner.invoke(app, ["secrets", "--help"])
    assert res.exit_code == 0

def test_012_gpu_help():
    res = runner.invoke(app, ["gpu", "--help"])
    assert res.exit_code == 0

def test_013_scan_help():
    res = runner.invoke(app, ["scan", "--help"])
    assert res.exit_code == 0

def test_014_redact_help():
    res = runner.invoke(app, ["redact", "--help"])
    assert res.exit_code == 0

def test_015_table_help():
    res = runner.invoke(app, ["table", "--help"])
    assert res.exit_code == 0

# ----------------------------------------------------
# 16-35: Memory & SQLite Learning Tests
# ----------------------------------------------------
def test_016_init_memory_db():
    init_memory_db()
    memories = get_all_memories()
    assert isinstance(memories, list)

def test_017_clear_memories():
    clear_memories()
    assert len(get_all_memories()) == 0

def test_018_add_single_memory():
    clear_memories()
    add_memory("preference", "Prefer Python 3.14")
    m = get_all_memories()
    assert len(m) == 1
    assert m[0]["content"] == "Prefer Python 3.14"

def test_019_add_multiple_memories():
    clear_memories()
    add_memory("pref1", "Use pacman")
    add_memory("pref2", "Use yay")
    add_memory("pref3", "Use reflector")
    assert len(get_all_memories()) == 3

def test_020_memory_id_field():
    clear_memories()
    add_memory("cat", "Test Rule")
    m = get_all_memories()[0]
    assert "id" in m and isinstance(m["id"], int)

def test_021_memory_created_at_field():
    clear_memories()
    add_memory("cat", "Test Rule")
    m = get_all_memories()[0]
    assert "created_at" in m

def test_022_cli_memory_add():
    res = runner.invoke(app, ["memory", "add", "CLI Test Rule"])
    assert res.exit_code == 0
    assert "Saved to background memory" in res.output

def test_023_cli_memory_list():
    res = runner.invoke(app, ["memory", "list"])
    assert res.exit_code == 0

def test_024_cli_memory_clear():
    res = runner.invoke(app, ["memory", "clear"])
    assert res.exit_code == 0
    assert "cleared" in res.output

def test_025_cli_learn_alias():
    res = runner.invoke(app, ["learn", "list"])
    assert res.exit_code == 0

# ----------------------------------------------------
# 26-45: User Persona & Skill Distiller Tests
# ----------------------------------------------------
def test_026_get_user_profile():
    profile = get_user_profile()
    assert isinstance(profile, dict)
    assert "os" in profile

def test_027_update_user_profile():
    update_user_profile("test_key", "test_val")
    profile = get_user_profile()
    assert profile["test_key"] == "test_val"

def test_028_user_profile_learned_preferences():
    profile = get_user_profile()
    assert "learned_preferences" in profile
    assert isinstance(profile["learned_preferences"], list)

def test_029_create_auto_skill():
    create_auto_skill("test_skill_99", "Test Skill Description", "echo 'hello'")
    skills = list_auto_skills()
    skill_names = [s["name"] for s in skills]
    assert "test_skill_99" in skill_names

def test_030_list_auto_skills_returns_list():
    skills = list_auto_skills()
    assert isinstance(skills, list)

def test_031_cli_hermes_distill():
    res = runner.invoke(app, ["hermes", "distill"])
    assert res.exit_code == 0
    assert "Distilled new skill" in res.output

def test_032_cli_hermes_persona():
    res = runner.invoke(app, ["hermes", "persona"])
    assert res.exit_code == 0
    assert "Persona" in res.output

def test_033_cli_hermes_nudge():
    res = runner.invoke(app, ["hermes", "nudge", "Always verify tests"])
    assert res.exit_code == 0
    assert "persisted" in res.output

def test_034_cli_hermes_recall():
    res = runner.invoke(app, ["hermes", "recall", "verify"])
    assert res.exit_code == 0

def test_035_cli_hermes_daemon():
    res = runner.invoke(app, ["hermes", "daemon"])
    assert res.exit_code == 0
    assert "Daemon" in res.output

def test_036_cli_profile():
    res = runner.invoke(app, ["profile"])
    assert res.exit_code == 0

def test_037_cli_skills():
    res = runner.invoke(app, ["skills"])
    assert res.exit_code == 0

# ----------------------------------------------------
# 38-60: Redactor & Sanitizer Security Tests
# ----------------------------------------------------
def test_038_redact_sk_proj_key():
    res = runner.invoke(app, ["redact", "sk-proj-99999999999999999999"])
    assert "[REDACTED_API_KEY]" in res.output

def test_039_redact_github_token():
    res = runner.invoke(app, ["redact", "ghp_123456789012345678901234567890123456"])
    assert "[REDACTED_GITHUB_TOKEN]" in res.output

def test_040_redact_ip_address():
    res = runner.invoke(app, ["redact", "192.168.1.100"])
    assert "[REDACTED_IP_ADDRESS]" in res.output

def test_041_redact_password_pattern():
    res = runner.invoke(app, ["redact", "password: my_secret_pass"])
    assert "[REDACTED]" in res.output

def test_042_redact_clean_text():
    res = runner.invoke(app, ["redact", "Hello world from Arch Linux"])
    assert "Hello world from Arch Linux" in res.output

# ----------------------------------------------------
# 43-70: Rich Table Rendering & Visual UI Tests
# ----------------------------------------------------
def test_043_table_valid_json_list():
    json_data = '[{"ColA": "ValA", "ColB": "ValB"}]'
    res = runner.invoke(app, ["table", json_data])
    assert res.exit_code == 0
    assert "ValA" in res.output

def test_044_table_csv_data():
    csv_data = "Header1,Header2\nRow1Val,Row2Val"
    res = runner.invoke(app, ["table", csv_data])
    assert res.exit_code == 0
    assert "Row1Val" in res.output

def test_045_table_invalid_input():
    res = runner.invoke(app, ["table", "invalid input text"])
    assert res.exit_code == 0

def test_046_neofetch_command():
    res = runner.invoke(app, ["neofetch"])
    assert res.exit_code == 0
    assert "Dashboard" in res.output or "Arch Linux" in res.output

def test_047_dashboard_alias():
    res = runner.invoke(app, ["dashboard"])
    assert res.exit_code == 0

# ----------------------------------------------------
# 48-80: System Context & Prompt Cache Tests
# ----------------------------------------------------
def test_048_get_cached_system_prompt():
    prompt = get_cached_system_prompt("capture-help", ["Python"])
    assert "REAL-TIME SYSTEM ENVIRONMENT" in prompt
    assert "Current Year:" in prompt
    assert "Arch Linux" in prompt

def test_049_system_prompt_includes_memories():
    clear_memories()
    add_memory("test_cat", "Test Prompt Memory Rule 123")
    prompt = get_cached_system_prompt("capture-help", ["Python"])
    assert "Test Prompt Memory Rule 123" in prompt

# ----------------------------------------------------
# 50-100: Arch Linux & DevOps Commands Tests
# ----------------------------------------------------
def test_050_arch_info():
    res = runner.invoke(app, ["arch", "info"])
    assert res.exit_code == 0

def test_051_arch_pkg():
    res = runner.invoke(app, ["arch", "pkg", "neovim"])
    assert res.exit_code == 0

def test_052_arch_clean():
    res = runner.invoke(app, ["arch", "clean"])
    assert res.exit_code == 0

def test_053_arch_systemd():
    res = runner.invoke(app, ["arch", "systemd"])
    assert res.exit_code == 0

def test_054_arch_mirror():
    res = runner.invoke(app, ["arch", "mirror"])
    assert res.exit_code == 0

def test_055_gpu_monitor():
    res = runner.invoke(app, ["gpu"])
    assert res.exit_code == 0

def test_056_scan_security():
    res = runner.invoke(app, ["scan"])
    assert res.exit_code == 0

def test_057_docker_cmd():
    res = runner.invoke(app, ["docker"])
    assert res.exit_code == 0

def test_058_disk_cmd():
    res = runner.invoke(app, ["disk"])
    assert res.exit_code == 0

def test_059_firewall_cmd():
    res = runner.invoke(app, ["firewall"])
    assert res.exit_code == 0

def test_060_graph_cmd():
    res = runner.invoke(app, ["graph"])
    assert res.exit_code == 0

def test_061_guard_cmd(monkeypatch):
    class FakeResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kwargs):
        if cmd[0] == "pytest":
            return FakeResult()
        raise FileNotFoundError

    monkeypatch.setattr("subprocess.run", fake_run)
    res = runner.invoke(app, ["guard"])
    assert res.exit_code == 0

def test_062_update_cmd():
    res = runner.invoke(app, ["update"])
    assert res.exit_code == 0

def test_063_ensemble_cmd():
    res = runner.invoke(app, ["ensemble", "ping"])
    assert res.exit_code in [0, 1]

def test_064_local_list_cmd():
    res = runner.invoke(app, ["local", "list"])
    assert res.exit_code == 0

def test_065_summarize_help_cmd():
    res = runner.invoke(app, ["summarize", "--help"])
    assert res.exit_code == 0
    assert "summarize" in res.output

CORE_COMMANDS = [
    "ask", "chat", "index", "explain", "fix", "review", "docs", "commit",
    "test", "optimize", "alias", "history", "resume", "models", "config",
    "gpu", "ensemble", "redact", "update", "graph", "guard", "scan", "virus",
    "docker", "disk", "firewall", "neofetch", "table", "profile", "skills",
    "pr", "audit", "diagram", "script", "clean", "changelog", "benchmark",
    "refactor", "secrets", "translate", "stats", "web", "team", "tui",
    "plugin", "doctor", "summarize",
]

def test_066_all_core_commands_registered():
    names = {c.name for c in app.registered_commands}
    missing = [c for c in CORE_COMMANDS if c not in names]
    assert not missing, f"Commands missing from CLI: {missing}"

def test_067_sub_typers_registered():
    names = {group.name for group in app.registered_groups}
    for group in ["local", "arch", "memory", "learn", "hermes"]:
        assert group in names, f"Sub-command group '{group}' not registered"

def test_068_all_core_command_helps_exit_zero():
    for cmd in CORE_COMMANDS:
        res = runner.invoke(app, [cmd, "--help"])
        assert res.exit_code == 0, f"'{cmd} --help' failed: {res.output[:200]}"

def test_069_version_flag_matches_module():
    from capture_help import __version__
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert __version__ in res.stdout

def test_070_no_command_invokes_chat_header():
    res = runner.invoke(app, [])
    assert res.exit_code == 0
    assert "chat" in res.output.lower() or "capture-help" in res.output
