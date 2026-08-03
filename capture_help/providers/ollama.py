import sys
import time
from typing import Generator, List, Dict, Optional, Tuple
from openai import OpenAI, APIError, APIConnectionError
from rich.console import Console

from capture_help.provider import BaseLLMProvider
from capture_help.deepseek import TokenUsageStats

console = Console()

class OllamaProvider(BaseLLMProvider):
    """Local offline LLM Provider via Ollama API (http://localhost:11434/v1)."""

    def __init__(self, model: str = "qwen2.5-coder", base_url: str = "http://localhost:11434/v1"):
        self.model = model
        self.base_url = base_url
        self.client = OpenAI(
            api_key="ollama",
            base_url=self.base_url,
        )

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
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted,
                temperature=temperature,
                stream=True,
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content, None

            duration = time.time() - start_time
            stats = TokenUsageStats(
                duration_seconds=duration,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                model=f"ollama/{self.model}",
            )
            yield "", stats

        except APIConnectionError:
            console.print(f"\n[bold red]Local Ollama Error:[/bold red] Could not connect to Ollama server at {self.base_url}.\nMake sure Ollama is running (`ollama serve`).")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[bold red]Ollama Error:[/bold red] {str(e)}")
            sys.exit(1)

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
