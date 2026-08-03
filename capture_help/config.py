import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

CONFIG_DIR = Path.home() / ".config" / "capture-help"
CONFIG_FILE = CONFIG_DIR / ".env"

def init_config():
    """Load configuration from local .env or global ~/.config/capture-help/.env."""
    # 1. Local directory .env
    if Path(".env").exists():
        load_dotenv(Path(".env"), override=True)
    
    # 2. Global user config .env
    if CONFIG_FILE.exists():
        load_dotenv(CONFIG_FILE, override=False)

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

def save_config(api_key: str, base_url: Optional[str] = None, model: Optional[str] = None) -> Path:
    """Save API configuration to ~/.config/capture-help/.env."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    env_content = f"DEEPSEEK_API_KEY={api_key}\n"
    if base_url:
        env_content += f"DEEPSEEK_BASE_URL={base_url}\n"
    else:
        env_content += f"DEEPSEEK_BASE_URL={settings.deepseek_base_url}\n"
        
    if model:
        env_content += f"DEEPSEEK_MODEL={model}\n"
    else:
        env_content += f"DEEPSEEK_MODEL={settings.deepseek_model}\n"
        
    env_content += f"DEFAULT_PROVIDER={settings.default_provider}\n"

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(env_content)
        
    # Reload environment
    load_dotenv(CONFIG_FILE, override=True)
    return CONFIG_FILE
