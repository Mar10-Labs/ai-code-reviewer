import os
from typing import Optional

from src.llm.ports.llm_port import LLMPort, LLMConfig
from src.llm.adapters.groq_adapter import GroqAdapter
from src.llm.adapters.gemini_adapter import GeminiAdapter
from src.llm.adapters.ollama_adapter import OllamaAdapter
from src.llm.adapters.litellm_adapter import LiteLLMAdapter


class LLMFactory:
    """Factory for creating LLM adapters based on configuration.
    
    Uses LiteLLM as the unified adapter with provider-specific configurations.
    Falls back to individual adapters if LiteLLM is not available.
    """

    PROVIDER_MODELS = {
        "groq": {
            "standard": "groq/llama-3.3-70b-versatile",
            "premium": "groq/llama-3.3-70b-versatile",
        },
        "gemini": {
            "standard": "gemini/gemini-1.5-flash",
            "premium": "gemini/gemini-1.5-pro",
        },
        "ollama": {
            "standard": "ollama/llama3.2",
            "premium": "ollama/llama3.2",
        },
        "openai": {
            "standard": "openai/gpt-4o-mini",
            "premium": "openai/gpt-4o",
        },
        "anthropic": {
            "standard": "anthropic/claude-3-haiku-20240307",
            "premium": "anthropic/claude-3-5-sonnet-20241022",
        },
    }

    USE_LITELLM = os.getenv("USE_LITELLM", "true").lower() == "true"

    @classmethod
    def create(cls, provider: str = None) -> LLMPort:
        """Create an LLM adapter based on the provider"""
        provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()

        if cls.USE_LITELLM:
            return cls._create_litellm(provider)

        return cls._create_legacy(provider)

    @classmethod
    def _create_litellm(cls, provider: str) -> LLMPort:
        """Create a LiteLLM adapter for the given provider"""
        api_key = os.getenv(f"{provider.upper()}_API_KEY")
        base_url = os.getenv("LITELLM_BASE_URL")
        model = os.getenv(f"{provider.upper()}_MODEL")

        if model and "/" not in model:
            model = f"{provider}/{model}"

        return LiteLLMAdapter(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )

    @classmethod
    def _create_legacy(cls, provider: str) -> LLMPort:
        """Create legacy adapter for backward compatibility"""
        adapters = {
            "groq": cls._create_groq,
            "gemini": cls._create_gemini,
            "ollama": cls._create_ollama,
        }

        creator = adapters.get(provider)
        if not creator:
            raise ValueError(f"Unknown LLM provider: {provider}. Available: {list(adapters.keys())}")

        return creator()

    @classmethod
    def _create_groq(cls) -> LLMPort:
        model = os.getenv("GROQ_MODEL", cls.PROVIDER_MODELS["groq"]["standard"].split("/")[-1])
        return GroqAdapter(model=model)

    @classmethod
    def _create_gemini(cls) -> LLMPort:
        api_key = os.getenv("GEMINI_API_KEY")
        model = os.getenv("GEMINI_MODEL", cls.PROVIDER_MODELS["gemini"]["standard"].split("/")[-1])
        return GeminiAdapter(api_key=api_key, model=model)

    @classmethod
    def _create_ollama(cls) -> LLMPort:
        base_url = os.getenv("OLLAMA_BASE_URL")
        model = os.getenv("OLLAMA_MODEL", cls.PROVIDER_MODELS["ollama"]["standard"].split("/")[-1])
        return OllamaAdapter(base_url=base_url, model=model)

    @classmethod
    def create_standard(cls, provider: str = None) -> LLMPort:
        """Create standard model adapter"""
        provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        model = cls.PROVIDER_MODELS.get(provider, {}).get("standard")

        if cls.USE_LITELLM:
            return LiteLLMAdapter(provider=provider, model=model)

        creators = {
            "groq": lambda: GroqAdapter(model=model.split("/")[-1] if "/" in model else model),
            "gemini": lambda: GeminiAdapter(model=model.split("/")[-1] if "/" in model else model),
            "ollama": lambda: OllamaAdapter(model=model.split("/")[-1] if "/" in model else model),
        }

        creator = creators.get(provider)
        if creator:
            return creator()
        return creators["groq"]()

    @classmethod
    def create_premium(cls, provider: str = None) -> LLMPort:
        """Create premium model adapter for critical tasks"""
        provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        model = cls.PROVIDER_MODELS.get(provider, {}).get("premium")

        if cls.USE_LITELLM:
            return LiteLLMAdapter(provider=provider, model=model)

        creators = {
            "groq": lambda: GroqAdapter(model=model.split("/")[-1] if "/" in model else model),
            "gemini": lambda: GeminiAdapter(model=model.split("/")[-1] if "/" in model else model),
            "ollama": lambda: OllamaAdapter(model=model.split("/")[-1] if "/" in model else model),
        }

        creator = creators.get(provider)
        if creator:
            return creator()
        return creators["groq"]()

    @classmethod
    def get_available_providers(cls) -> list[dict]:
        """Get list of available providers with their status"""
        providers = []

        for provider_name, models in cls.PROVIDER_MODELS.items():
            adapter = LiteLLMAdapter(provider=provider_name)
            providers.append({
                "name": provider_name,
                "available": adapter.is_available(),
                "models": list(set([models.get("standard", ""), models.get("premium", "")])),
                "type": "litellm" if cls.USE_LITELLM else "legacy"
            })

        return providers


def get_llm() -> LLMPort:
    """Convenience function to get the configured LLM adapter"""
    return LLMFactory.create()


def get_standard_llm() -> LLMPort:
    """Convenience function to get standard LLM"""
    return LLMFactory.create_standard()


def get_premium_llm() -> LLMPort:
    """Convenience function to get premium LLM for critical tasks"""
    return LLMFactory.create_premium()
