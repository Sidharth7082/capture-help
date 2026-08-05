import pytest
from capture_help.persona import (
    Persona,
    activate_persona,
    get_active_persona,
    reset_persona,
    build_system_prompt,
    list_personas,
)
from capture_help.deepseek import DeepSeekProvider, DEEPSEEK_MODELS
from capture_help.config import save_config, settings


def test_gehrman_persona_activation_and_system_prompt():
    reset_persona()
    p = activate_persona("gehrman")
    assert p.name == "gehrman"
    assert p.display_name == "Gehrman Sparrow"

    base_prompt = "You are capture-help assistant."
    full_prompt = build_system_prompt(base_prompt)
    assert "CHARACTER OVERLAY ACTIVE: Gehrman Sparrow" in full_prompt
    assert "Cold, calculating" in full_prompt or "Gehrman" in full_prompt
    reset_persona()


def test_aggressive_persona_switching_matrix():
    personas = list_personas()
    assert len(personas) >= 1

    # Aggressive rapid switching loop
    for _ in range(20):
        activate_persona("gehrman")
        assert get_active_persona().name == "gehrman"
        reset_persona()
        assert get_active_persona() is None


def test_provider_auto_routing_and_config():
    # Test Cloud model auto-routing
    provider_cloud = DeepSeekProvider(
        api_key="sk-test-00000000000000000000",
        base_url="http://localhost:11434/v1",
        model="deepseek-v4-flash",
    )
    assert provider_cloud.base_url == "https://api.deepseek.com"

    # Test Local Gemma auto-routing
    provider_local = DeepSeekProvider(
        api_key="",
        base_url="https://api.deepseek.com",
        model="gemma3:12b",
    )
    assert provider_local.base_url == "http://localhost:11434/v1"
