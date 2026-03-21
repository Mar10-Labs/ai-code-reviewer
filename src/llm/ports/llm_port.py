from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    providers_tried: list[str] = None
    is_fallback: bool = False
    fallback_reason: Optional[str] = None
    
    def __post_init__(self):
        if self.providers_tried is None:
            self.providers_tried = []


@dataclass
class LLMConfig:
    model: str
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 60


class LLMPort(ABC):
    """Input Port - Interface for LLM providers"""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name (e.g., 'groq', 'gemini', 'ollama')"""
        pass

    @abstractmethod
    async def complete(self, prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
        """Send a completion request to the LLM"""
        pass

    @abstractmethod
    async def complete_structured(
        self, 
        prompt: str, 
        schema: dict,
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """Send a completion request expecting structured output (JSON)"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available/configured"""
        pass
