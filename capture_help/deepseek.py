import sys
from typing import Generator, List, Dict, Optional
from openai import OpenAI, APIError, AuthenticationError, APIConnectionError
from rich.console import Console

from capture_help.config import settings
from capture_help.provider import BaseLLMProvider

console = Console()

class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API Provider utilizing OpenAI python SDK."""

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

    def stream_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Generator[str, None, None]:
        formatted_messages = self._prepare_messages(messages, system_prompt)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=temperature,
                stream=True,
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
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
    ) -> str:
        chunks = list(self.stream_completion(messages, system_prompt=system_prompt, temperature=temperature))
        return "".join(chunks)

def get_provider() -> BaseLLMProvider:
    """Factory function to get configured LLM provider."""
    # Extensible for future providers like OpenAI or OpenRouter
    if settings.default_provider.lower() == "deepseek":
        return DeepSeekProvider()
    return DeepSeekProvider()
