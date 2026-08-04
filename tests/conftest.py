import importlib
import pkgutil
import shutil

import pytest

import capture_help.commands as commands_pkg
import capture_help.config as config_mod
import capture_help.deepseek as deepseek

MOCK_OUTPUT = "## Mocked Offline Output\n\nGenerated without a network call."


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect config writes (and the personas dir) to a temp location.

    Without this, tests that call `save_config` would overwrite the user's real
    ~/.config/capture-help/.env (wiping their DeepSeek API key). Everything runs
    against tmp_path instead. Personas bundled with the real install are copied
    in so persona-dependent tests still find them.
    """
    import capture_help.persona as persona_mod

    real_config_dir = config_mod.CONFIG_DIR
    real_personas_dir = persona_mod.PERSONAS_DIR

    cfg = tmp_path / "config"
    monkeypatch.setattr(config_mod, "CONFIG_DIR", cfg)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", cfg / ".env")
    monkeypatch.setattr(persona_mod, "CONFIG_DIR", cfg)
    monkeypatch.setattr(persona_mod, "PERSONAS_DIR", cfg / "personas")
    monkeypatch.setattr(persona_mod, "ACTIVE_PERSONA_FILE", cfg / "active_persona")

    if real_personas_dir.exists():
        shutil.copytree(real_personas_dir, cfg / "personas", dirs_exist_ok=True)


class FakeProvider:
    """Deterministic offline stand-in for LLM providers (no network calls)."""

    def stream_completion(self, messages, system_prompt=None, temperature=0.7):
        yield MOCK_OUTPUT, None

    def completion(self, messages, system_prompt=None, temperature=0.7):
        return MOCK_OUTPUT, None


def _fake_provider(*args, **kwargs):
    return FakeProvider()


def _command_modules():
    yield commands_pkg
    for mod in pkgutil.walk_packages(commands_pkg.__path__, prefix=commands_pkg.__name__ + "."):
        try:
            yield importlib.import_module(mod.name)
        except Exception:
            continue


@pytest.fixture(autouse=True)
def offline_provider(monkeypatch):
    """Redirect every command's provider into a fake so no test hits the network.

    Patches the per-module `get_provider` / `ask_deepseek` references. The real
    `capture_help.deepseek.get_provider` is left untouched so routing tests
    (tests/test_provider_routing.py) can still exercise it.
    """
    for mod in _command_modules():
        if hasattr(mod, "get_provider"):
            monkeypatch.setattr(mod, "get_provider", _fake_provider)
        if hasattr(mod, "ask_deepseek"):
            monkeypatch.setattr(mod, "ask_deepseek", lambda *a, **k: MOCK_OUTPUT)
    monkeypatch.setattr(deepseek, "ask_deepseek", lambda *a, **k: MOCK_OUTPUT)
