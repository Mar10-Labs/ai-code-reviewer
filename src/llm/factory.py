import os
from typing import Optional

from src.llm.ports.llm_port import LLMPort
from src.llm.adapters.llm_adapter import LLMAdapter


class LLMFactory:
    """Factory for creating LLM adapters"""

    @classmethod
    def create(cls, provider: str = None) -> LLMPort:
        """Create an LLM adapter based on the provider"""
        provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        model = os.getenv("LLM_MODEL")
        return LLMAdapter(provider=provider, model=model)

    @classmethod
    def create_standard(cls, provider: str = None) -> LLMPort:
        """Create standard model adapter"""
        provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        adapter = LLMAdapter(provider=provider)
        adapter.model = adapter.PROVIDERS.get(provider, {}).get("standard_model", adapter.model)
        return adapter

    @classmethod
    def create_premium(cls, provider: str = None) -> LLMPort:
        """Create premium model adapter for critical tasks"""
        provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        adapter = LLMAdapter(provider=provider)
        adapter.model = adapter.PROVIDERS.get(provider, {}).get("premium_model", adapter.model)
        return adapter

    @classmethod
    def get_available_providers(cls) -> list[dict]:
        """Get list of available providers with their status"""
        providers = []
        
        for provider_name in LLMAdapter.PROVIDERS.keys():
            adapter = LLMAdapter(provider=provider_name)
            providers.append({
                "name": provider_name,
                "available": adapter.is_available(),
                "models": [adapter.model],
                "standard_model": adapter.PROVIDERS[provider_name].get("standard_model"),
                "premium_model": adapter.PROVIDERS[provider_name].get("premium_model"),
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
