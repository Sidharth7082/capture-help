import pytest
from openai import APIError

from capture_help import deepseek
from capture_help.config import CONFIG_FILE, save_config
from capture_help.provider import ProviderError
from capture_help.providers.ollama import OllamaProvider


def test_default_provider_ollama_routes_to_local(monkeypatch):
    monkeypatch.setenv("DEFAULT_PROVIDER", "ollama")
    monkeypatch.setenv("DEEPSEEK_MODEL", "qwen2.5-coder:14b")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://localhost:11434/v1")
    p = deepseek.get_provider()
    assert isinstance(p, OllamaProvider)
    assert p.model == "qwen2.5-coder:14b"


def test_ollama_tagged_model_routes_to_local(monkeypatch):
    monkeypatch.setenv("DEFAULT_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_MODEL", "llama3.3:70b")
    p = deepseek.get_provider()
    assert isinstance(p, OllamaProvider)


def test_cloud_deepseek_routes_to_cloud(monkeypatch):
    monkeypatch.setenv("DEFAULT_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-123456")
    p = deepseek.get_provider()
    assert type(p).__name__ == "DeepSeekProvider"


def test_ollama_provider_url_fallback():
    p = OllamaProvider(model="gemma3:12b", base_url="https://api.deepseek.com")
    assert "localhost:11434" in p.base_url


def test_ollama_ping_returns_bool():
    assert isinstance(OllamaProvider.ping(timeout=0.5), bool)


def test_ollama_provider_raises_on_error(monkeypatch):
    """Provider failures raise ProviderError (not sys.exit) so chat survives."""
    class FakeCreate:
        def create(self, *args, **kwargs):
            raise APIError("model not found", response=None, body=None)

    class FakeClient:
        chat = FakeCreate()

    p = OllamaProvider(model="missing-model:1b", base_url="http://localhost:11434/v1")
    monkeypatch.setattr(p, "client", FakeClient())

    with pytest.raises(ProviderError):
        for _ in p.stream_completion([{"role": "user", "content": "hi"}]):
            pass


def test_deepseek_provider_raises_on_error(monkeypatch):
    class FakeCreate:
        def create(self, *args, **kwargs):
            raise APIError("some api error", response=None, body=None)

    class FakeClient:
        chat = FakeCreate()

    p = deepseek.DeepSeekProvider(api_key="sk-test-key-123456")
    monkeypatch.setattr(p, "client", FakeClient())

    with pytest.raises(ProviderError):
        for _ in p.stream_completion([{"role": "user", "content": "hi"}]):
            pass


def test_save_config_keep_key_preserves_existing_key(tmp_path, monkeypatch):
    """The local-fallback path must never wipe the configured DeepSeek API key."""
    from capture_help import config as config_mod

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-keep-me-123456789")
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / ".env")

    save_config(api_key="", provider="ollama", model="gemma3:12b", keep_key=True)

    content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-keep-me-123456789" in content


def test_save_config_without_keep_key_still_allows_clearing(tmp_path, monkeypatch):
    from capture_help import config as config_mod

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-keep-me-123456789")
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / ".env")

    save_config(api_key="", provider="ollama", model="gemma3:12b", keep_key=False)

    content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=" in content
