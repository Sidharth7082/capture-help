import sys
import time
from dataclasses import dataclass
from typing import Generator, List, Dict, Optional, Tuple
from openai import OpenAI, APIError, AuthenticationError, APIConnectionError
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

class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API Provider utilizing OpenAI python SDK with usage tracking."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.deepseek_api_key
        self.base_url = base_url or settings.deepseek_base_url
        self.model = model or settings.deepseek_model

        if not self.api_key:
            console.print(
                "[bold red]Error:[/bold red] DeepSeek API Key not found!\n"
                "[yellow]Please run 'capture-help config' or set DEEPSEEK_API_KEY in your environment or .env file.[/yellow]"
            )
            sys.exit(1)

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def _prepare_messages(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        formatted = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        formatted.extend(messages)
        return formatted

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # DeepSeek pricing: $0.14 per 1M input tokens, $0.28 per 1M output tokens
        input_cost = (prompt_tokens / 1_000_000) * 0.14
        output_cost = (completion_tokens / 1_000_000) * 0.28
        return input_cost + output_cost

    def stream_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Generator[Tuple[str, Optional[TokenUsageStats]], None, None]:
        formatted_messages = self._prepare_messages(messages, system_prompt)
        start_time = time.time()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=temperature,
                stream=True,
                stream_options={"include_usage": True}
            )
            
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            for chunk in response:
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    total_tokens = chunk.usage.total_tokens

                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content, None

            duration = time.time() - start_time
            # Fallback estimation if usage stats not provided by stream
            if total_tokens == 0:
                prompt_text = "".join(m["content"] for m in formatted_messages)
                prompt_tokens = max(1, len(prompt_text) // 4)
                total_tokens = prompt_tokens + completion_tokens

            cost = self.calculate_cost(prompt_tokens, completion_tokens)
            stats = TokenUsageStats(
                duration_seconds=duration,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
                model=self.model,
            )
            yield "", stats

        except AuthenticationError:
            console.print("\n[bold red]API Error:[/bold red] Invalid DeepSeek API key. Please check your credentials using 'capture-help config'.")
            sys.exit(1)
        except APIConnectionError:
            console.print("\n[bold red]Network Error:[/bold red] Could not connect to DeepSeek API endpoint at " + self.base_url)
            sys.exit(1)
        except APIError as e:
            console.print(f"\n[bold red]DeepSeek API Error:[/bold red] {e.message}")
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
        for chunk, stats in self.stream_completion(messages, system_prompt=system_prompt, temperature=temperature):
            if chunk:
                text_chunks.append(chunk)
            if stats:
                final_stats = stats
        return "".join(text_chunks), final_stats

def get_provider() -> BaseLLMProvider:
    return DeepSeekProvider()
