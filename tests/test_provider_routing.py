from capture_help import deepseek
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
