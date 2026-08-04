import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

CONFIG_DIR = Path.home() / ".config" / "capture-help"
CONFIG_FILE = CONFIG_DIR / ".env"

def init_config():
    """Load configuration from global ~/.config/capture-help/.env or local .env."""
    # 1. Global user config .env (takes precedence for user settings)
    if CONFIG_FILE.exists():
        load_dotenv(CONFIG_FILE, override=True)

    # 2. Local directory .env (fallback)
    if Path(".env").exists():
        load_dotenv(Path(".env"), override=False)


init_config()


class Settings:
    @property
    def deepseek_api_key(self) -> str:
        return os.getenv("DEEPSEEK_API_KEY", "")

    @property
    def deepseek_base_url(self) -> str:
        return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    @property
    def deepseek_model(self) -> str:
        return os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    @property
    def default_provider(self) -> str:
        return os.getenv("DEFAULT_PROVIDER", "deepseek")


settings = Settings()


def save_config(api_key: str, base_url: Optional[str] = None, model: Optional[str] = None, provider: Optional[str] = None) -> Path:
    """Save API configuration to ~/.config/capture-help/.env and update live process environment."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    prov = provider if provider else settings.default_provider
    target_model = model if model else settings.deepseek_model

    if not base_url:
        if prov == "ollama" or "gemma" in target_model.lower():
            target_url = "http://localhost:11434/v1"
        else:
            target_url = "https://api.deepseek.com"
    else:
        target_url = base_url

    # Update in-memory process environment immediately
    os.environ["DEEPSEEK_API_KEY"] = api_key
    os.environ["DEEPSEEK_BASE_URL"] = target_url
    os.environ["DEEPSEEK_MODEL"] = target_model
    os.environ["DEFAULT_PROVIDER"] = prov

    env_content = f"DEEPSEEK_API_KEY={api_key}\n"
    env_content += f"DEEPSEEK_BASE_URL={target_url}\n"
    env_content += f"DEEPSEEK_MODEL={target_model}\n"
    env_content += f"DEFAULT_PROVIDER={prov}\n"

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(env_content)

    # Reload environment
    load_dotenv(CONFIG_FILE, override=True)
    return CONFIG_FILE
