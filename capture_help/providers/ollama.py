import time
from typing import Generator, List, Dict, Optional, Tuple
from openai import OpenAI, APIError, APIConnectionError
from rich.console import Console

from capture_help.provider import BaseLLMProvider, ProviderError
from capture_help.deepseek import TokenUsageStats

console = Console()

DEFAULT_OLLAMA_URL = "http://localhost:11434/v1"

class OllamaProvider(BaseLLMProvider):
    """Local offline LLM Provider via Ollama API (http://localhost:11434/v1)."""

    def __init__(self, model: str = "qwen2.5-coder", base_url: str = DEFAULT_OLLAMA_URL):
        self.model = model
        # Never let a stale DeepSeek cloud URL leak through to the local server.
        if not base_url or "api.deepseek.com" in base_url:
            self.base_url = DEFAULT_OLLAMA_URL
        else:
            self.base_url = base_url
        self.client = OpenAI(
            api_key="ollama",
            base_url=self.base_url,
        )

    @staticmethod
    def ping(timeout: float = 2.0) -> bool:
        """Check whether a local Ollama server is reachable."""
        try:
            import httpx
            res = httpx.get("http://localhost:11434/api/tags", timeout=timeout)
            return res.status_code == 200
        except Exception:
            return False

    @staticmethod
    def installed_models(timeout: float = 2.0) -> list:
        """List model names currently installed in Ollama."""
        try:
            import httpx
            res = httpx.get("http://localhost:11434/api/tags", timeout=timeout)
            if res.status_code == 200:
                return [m.get("name") for m in res.json().get("models", [])]
        except Exception:
            pass
        return []

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
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content, None

            duration = time.time() - start_time
            stats = TokenUsageStats(
                duration_seconds=duration,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost_usd=0.0,
                model=f"ollama/{self.model}",
            )
            yield "", stats

        except APIConnectionError:
            console.print(f"\n[bold red]Local Ollama Error:[/bold red] Could not connect to Ollama server at {self.base_url}.\nMake sure Ollama is running (`ollama serve`).")
            raise ProviderError(f"Ollama server unreachable at {self.base_url}")
        except APIError as e:
            message = str(getattr(e, "message", "") or e)
            if "not found" in message.lower() and "model" in message.lower():
                installed = ", ".join(OllamaProvider.installed_models()) or "(none)"
                console.print(
                    f"\n[bold red]Model '{self.model}' is not installed in Ollama.[/bold red]\n"
                    f"[bold cyan]Installed models:[/bold cyan] [bold white]{installed}[/bold white]\n"
                    f"[bold yellow]Fix:[/bold yellow] run [bold white]capture-help local use <model>[/bold white] "
                    f"(e.g. [bold white]capture-help local use gemma3:12b[/bold white])\n"
                    f"      or pull it with [bold white]ollama pull {self.model}[/bold white]"
                )
                raise ProviderError(f"model '{self.model}' not installed locally")
            console.print(f"\n[bold red]Ollama Error:[/bold red] {message}")
            raise ProviderError(message)
        except Exception as e:
            console.print(f"\n[bold red]Ollama Error:[/bold red] {str(e)}")
            raise ProviderError(str(e))

    def completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Tuple[str, Optional[TokenUsageStats]]:
        chunks = []
        final_stats = None
        for chunk, stats in self.stream_completion(messages, system_prompt, temperature):
            if chunk:
                chunks.append(chunk)
            if stats:
                final_stats = stats
        return "".join(chunks), final_stats
