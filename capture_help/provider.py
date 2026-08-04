from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Any, Optional


class ProviderError(Exception):
    """Raised when an LLM provider fails to produce a response.

    Unlike a hard sys.exit, this lets callers (e.g. the interactive chat)
    catch the failure and keep running instead of killing the session.
    """


class BaseLLMProvider(ABC):
    """Abstract Base Class for LLM Providers (DeepSeek, OpenAI, OpenRouter)."""

    @abstractmethod
    def stream_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Generator[str, None, None]:
        """Stream response chunks from the LLM provider."""
        pass

    @abstractmethod
    def completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Get complete response string from the LLM provider."""
        pass
