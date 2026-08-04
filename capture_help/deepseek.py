import os
import sys
import time
from typing import Generator, List, Dict, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI, APIError, APIConnectionError
from rich.console import Console

from capture_help.config import settings
from capture_help.provider import BaseLLMProvider

console = Console()

@dataclass
class TokenUsageStats:
    duration_seconds: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    model: str
    cache_hit_tokens: int = 0

DEEPSEEK_MODELS = {
    "deepseek-v4-flash": {
        "name": "DeepSeek V4-Flash",
        "description": "Ultra-fast, lowest cost beta model ($0.07 / 1M input tokens)",
        "input_cost_per_m": 0.07,
        "output_cost_per_m": 0.14,
        "cache_cost_per_m": 0.014,
    },
    "deepseek-chat": {
        "name": "DeepSeek Chat (V3)",
        "description": "Standard balanced code & conversation model ($0.14 / 1M input tokens)",
        "input_cost_per_m": 0.14,
        "output_cost_per_m": 0.28,
        "cache_cost_per_m": 0.014,
    },
    "deepseek-coder": {
        "name": "DeepSeek Coder",
        "description": "Specialized code generation & refactoring model ($0.14 / 1M input tokens)",
        "input_cost_per_m": 0.14,
        "output_cost_per_m": 0.28,
        "cache_cost_per_m": 0.014,
    },
    "deepseek-reasoner": {
        "name": "DeepSeek Reasoner (R1)",
        "description": "DeepSeek-R1 reasoning model for complex architectural problems",
        "input_cost_per_m": 0.55,
        "output_cost_per_m": 2.19,
        "cache_cost_per_m": 0.14,
    },
    "gemma3:12b": {
        "name": "Google Gemma 3 12B (Q4)",
        "description": "Google Gemma 3 12B 4-bit quantized local model ($0.00 / FREE Local Ollama)",
        "input_cost_per_m": 0.00,
        "output_cost_per_m": 0.00,
        "cache_cost_per_m": 0.00,
    },
    "gemma3:27b": {
        "name": "Google Gemma 3 27B (Q4)",
        "description": "Google Gemma 3 27B 4-bit quantized local model ($0.00 / FREE Local Ollama)",
        "input_cost_per_m": 0.00,
        "output_cost_per_m": 0.00,
        "cache_cost_per_m": 0.00,
    },
}

class DeepSeekProvider(BaseLLMProvider):
    """Official DeepSeek & Local Ollama API Provider implementation."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.deepseek_api_key
        self.base_url = base_url or settings.deepseek_base_url
        self.model = model or settings.deepseek_model

        if "gemma" in self.model.lower():
            # Local Ollama endpoint support for Gemma 3
            if "api.deepseek.com" in self.base_url:
                self.base_url = "http://localhost:11434/v1"
            if not self.api_key:
                self.api_key = "ollama"
        else:
            # Cloud DeepSeek models must route to https://api.deepseek.com if base_url is currently pointing to local Ollama
            if "localhost" in self.base_url or "127.0.0.1" in self.base_url or "11434" in self.base_url:
                self.base_url = "https://api.deepseek.com"

        if not self.api_key and "gemma" not in self.model.lower():
            console.print("\n[bold red]Error: DeepSeek API Key not found![/bold red]")
            console.print("Please run '[bold white]capture-help config --key YOUR_API_KEY[/bold white]' or set DEEPSEEK_API_KEY in your environment.")
            sys.exit(1)

        self.client = OpenAI(
            api_key=self.api_key or "ollama",
            base_url=self.base_url,
        )

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int, cache_hit_tokens: int = 0) -> float:
        pricing = DEEPSEEK_MODELS.get(self.model, {"input_cost_per_m": 0.0, "cache_cost_per_m": 0.0, "output_cost_per_m": 0.0})
        
        miss_tokens = max(0, prompt_tokens - cache_hit_tokens)
        input_cost = (miss_tokens / 1_000_000) * pricing["input_cost_per_m"]
        cache_cost = (cache_hit_tokens / 1_000_000) * pricing["cache_cost_per_m"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output_cost_per_m"]
        
        return input_cost + cache_cost + output_cost

    def stream_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Generator[Tuple[str, Optional[TokenUsageStats]], None, None]:
        formatted = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        formatted.extend(messages)

        start_time = time.time()
        prompt_tokens = 0
        completion_tokens = 0
        cache_hit_tokens = 0

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted,
                temperature=temperature,
                stream=True,
                stream_options={"include_usage": True},
            )

            for chunk in response:
                if hasattr(chunk, "usage") and chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    if hasattr(chunk.usage, "prompt_tokens_details") and chunk.usage.prompt_tokens_details:
                        cache_hit_tokens = getattr(chunk.usage.prompt_tokens_details, "cached_tokens", 0)

                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    content_piece = chunk.choices[0].delta.content
                    yield content_piece, None

            duration = time.time() - start_time
            total_tokens = prompt_tokens + completion_tokens
            cost = self.calculate_cost(prompt_tokens, completion_tokens, cache_hit_tokens)

            stats = TokenUsageStats(
                duration_seconds=duration,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
                model=self.model,
                cache_hit_tokens=cache_hit_tokens,
            )
            yield "", stats

        except APIConnectionError:
            console.print("\n[bold red]Network Error:[/bold red] Could not connect to API at " + self.base_url)
            sys.exit(1)
        except APIError as e:
            console.print(f"\n[bold red]API Error:[/bold red] {e.message}")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[bold red]Unexpected Error:[/bold red] {str(e)}")
            sys.exit(1)

    def completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Tuple[str, Optional[TokenUsageStats]]:
        text_chunks = []
        final_stats = None
        for chunk, stats in self.stream_completion(messages, system_prompt, temperature):
            if chunk:
                text_chunks.append(chunk)
            if stats:
                final_stats = stats
        return "".join(text_chunks), final_stats

def get_provider(model: Optional[str] = None) -> BaseLLMProvider:
    """Return the configured provider.

    Respects DEFAULT_PROVIDER (deepseek | ollama) so every command can run
    against local Ollama models. Also treats Ollama-tagged models
    (e.g. "qwen2.5-coder:14b", "gemma3:12b") and localhost base URLs as local.
    """
    from capture_help.providers.ollama import OllamaProvider

    target_model = (model or settings.deepseek_model).lower()
    base = settings.deepseek_base_url.lower()
    is_local = (
        settings.default_provider == "ollama"
        or ":" in target_model
        or "localhost" in base
        or "127.0.0.1" in base
        or "11434" in base
    )
    if is_local:
        return OllamaProvider(model=model or settings.deepseek_model, base_url=settings.deepseek_base_url)
    return DeepSeekProvider(model=model)

def ask_deepseek(prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None) -> str:
    provider = get_provider(model=model)
    response, _ = provider.completion([{"role": "user", "content": prompt}], system_prompt=system_prompt)
    return response

