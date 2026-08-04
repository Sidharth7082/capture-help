import json
import pytest
from typer.testing import CliRunner

from capture_help import persona as persona_mod
from capture_help.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(persona_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(persona_mod, "PERSONAS_DIR", tmp_path / "personas")
    monkeypatch.setattr(persona_mod, "ACTIVE_PERSONA_FILE", tmp_path / "active_persona")
    yield tmp_path


def test_persona_list_default():
    res = runner.invoke(app, ["persona", "list"])
    assert res.exit_code == 0
    assert "(default)" in res.output


def test_persona_create_from_template():
    res = runner.invoke(app, ["persona", "create", "aggr", "--template", "aggressive"])
    assert res.exit_code == 0
    p = persona_mod.get_persona("aggr")
    assert "zero fluff" in p.system_prompt


def test_persona_create_no_injected_limits():
    """Newly created personas carry no refusal/safety lines from the tool itself."""
    res = runner.invoke(app, ["persona", "create", "edge", "--template", "senior"])
    assert res.exit_code == 0
    prompt = persona_mod.get_persona("edge").system_prompt.lower()
    for banned in ("harmful", "decline", "refuse", "unsafe", "break character"):
        assert banned not in prompt


def test_persona_create_invalid_name():
    res = runner.invoke(app, ["persona", "create", "bad name!", "--template", "aggressive"])
    assert res.exit_code == 1


def test_persona_activate_and_active_file():
    runner.invoke(app, ["persona", "create", "sen", "--template", "senior"])
    res = runner.invoke(app, ["persona", "activate", "sen"])
    assert res.exit_code == 0
    assert persona_mod.get_active_persona().name == "sen"


def test_persona_reset():
    runner.invoke(app, ["persona", "create", "sen", "--template", "senior"])
    runner.invoke(app, ["persona", "activate", "sen"])
    res = runner.invoke(app, ["persona", "reset"])
    assert res.exit_code == 0
    assert persona_mod.get_active_persona() is None


def test_persona_export_import_roundtrip(tmp_path):
    runner.invoke(app, ["persona", "create", "keep", "--template", "aggressive"])
    out_file = tmp_path / "keep.json"
    res = runner.invoke(app, ["persona", "export", "keep", "--out", str(out_file)])
    assert res.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["name"] == "keep"

    runner.invoke(app, ["persona", "delete", "keep"])
    with pytest.raises(persona_mod.PersonaError):
        persona_mod.get_persona("keep")
    res = runner.invoke(app, ["persona", "import", str(out_file)])
    assert res.exit_code == 0
    assert persona_mod.get_persona("keep").name == "keep"


def test_persona_delete_active_resets():
    runner.invoke(app, ["persona", "create", "tmp1", "--template", "aggressive"])
    runner.invoke(app, ["persona", "activate", "tmp1"])
    runner.invoke(app, ["persona", "delete", "tmp1"])
    assert persona_mod.get_active_persona() is None


def test_persona_show_unknown_fails():
    res = runner.invoke(app, ["persona", "show", "nope"])
    assert res.exit_code == 1


def test_chat_persona_unknown_exits_without_loop():
    res = runner.invoke(app, ["chat", "--persona", "does-not-exist"])
    assert res.exit_code == 1
    assert "No persona named" in res.output


def test_chat_persona_flag_help():
    res = runner.invoke(app, ["chat", "--help"])
    assert res.exit_code == 0
    assert "--persona" in res.output
