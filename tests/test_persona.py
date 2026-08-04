import json
import pytest

from capture_help import persona as persona_mod


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect all persona storage to a temp dir for each test."""
    monkeypatch.setattr(persona_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(persona_mod, "PERSONAS_DIR", tmp_path / "personas")
    monkeypatch.setattr(persona_mod, "ACTIVE_PERSONA_FILE", tmp_path / "active_persona")
    yield tmp_path


def write_persona(dir_path, name="gehrman", **overrides):
    data = {
        "name": name,
        "display_name": "Gehrman Sparrow",
        "system_prompt": "Be cold and terse.",
        "description": "test persona",
        "greeting": "Say what you need.",
        "tags": ["fiction"],
    }
    data.update(overrides)
    personas_dir = dir_path / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    path = personas_dir / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_get_persona_valid(isolated_config):
    write_persona(isolated_config)
    p = persona_mod.get_persona("gehrman")
    assert p.display_name == "Gehrman Sparrow"
    assert p.system_prompt == "Be cold and terse."


def test_get_persona_missing_raises(isolated_config):
    with pytest.raises(persona_mod.PersonaError):
        persona_mod.get_persona("does_not_exist")


def test_get_persona_malformed_raises(isolated_config):
    personas_dir = isolated_config / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    (personas_dir / "broken.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(persona_mod.PersonaError):
        persona_mod.get_persona("broken")


def test_get_persona_missing_required_field(isolated_config):
    personas_dir = isolated_config / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    (personas_dir / "incomplete.json").write_text(
        json.dumps({"name": "incomplete"}), encoding="utf-8"
    )
    with pytest.raises(persona_mod.PersonaError):
        persona_mod.get_persona("incomplete")


def test_list_personas_skips_malformed(isolated_config):
    write_persona(isolated_config, name="gehrman")
    personas_dir = isolated_config / "personas"
    (personas_dir / "broken.json").write_text("not json", encoding="utf-8")
    result = persona_mod.list_personas()
    assert len(result) == 1
    assert result[0].name == "gehrman"


def test_activate_and_get_active_persona(isolated_config):
    write_persona(isolated_config)
    activated = persona_mod.activate_persona("gehrman")
    assert activated.name == "gehrman"

    active = persona_mod.get_active_persona()
    assert active is not None
    assert active.name == "gehrman"


def test_activate_invalid_persona_raises(isolated_config):
    with pytest.raises(persona_mod.PersonaError):
        persona_mod.activate_persona("nope")


def test_reset_persona_clears_active(isolated_config):
    write_persona(isolated_config)
    persona_mod.activate_persona("gehrman")
    assert persona_mod.get_active_persona() is not None

    persona_mod.reset_persona()
    assert persona_mod.get_active_persona() is None


def test_get_active_persona_none_by_default(isolated_config):
    assert persona_mod.get_active_persona() is None


def test_active_persona_file_stale_falls_back_to_default(isolated_config):
    write_persona(isolated_config)
    persona_mod.activate_persona("gehrman")

    # Simulate the persona file being deleted after activation.
    (isolated_config / "personas" / "gehrman.json").unlink()

    active = persona_mod.get_active_persona()
    assert active is None
    # And it should have self-healed by clearing the active pointer.
    assert not persona_mod.ACTIVE_PERSONA_FILE.exists()


def test_build_system_prompt_no_persona_returns_base(isolated_config):
    base = "You are capture-help, a terminal coding agent."
    assert persona_mod.build_system_prompt(base) == base


def test_build_system_prompt_layers_persona_on_base(isolated_config):
    write_persona(isolated_config)
    persona_mod.activate_persona("gehrman")

    base = "You are capture-help, a terminal coding agent."
    result = persona_mod.build_system_prompt(base)

    assert base in result
    assert "Be cold and terse." in result
    assert "Gehrman Sparrow" in result


def test_render_banner_includes_greeting(isolated_config):
    write_persona(isolated_config)
    p = persona_mod.get_persona("gehrman")
    banner = persona_mod.render_banner(p)
    assert "Gehrman Sparrow" in banner
    assert "Say what you need." in banner
