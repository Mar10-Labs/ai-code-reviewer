import os
from typing import Optional

from src.llm.ports.llm_port import LLMPort, LLMConfig
from src.llm.adapters.groq_adapter import GroqAdapter
from src.llm.adapters.gemini_adapter import GeminiAdapter
from src.llm.adapters.ollama_adapter import OllamaAdapter


class LLMFactory:
    """Factory for creating LLM adapters based on configuration"""

    PROVIDER_MODELS = {
        "groq": {
            "standard": "llama-3.3-70b-versatile",
            "premium": "llama-3.3-70b-versatile",
        },
        "gemini": {
            "standard": "gemini-1.5-flash",
            "premium": "gemini-1.5-pro",
        },
        "ollama": {
            "standard": "llama3.2",
            "premium": "llama3.2",
        },
    }

    @classmethod
    def create(cls, provider: str = None) -> LLMPort:
        """Create an LLM adapter based on the provider"""
        provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()

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
        model = os.getenv("GROQ_MODEL", cls.PROVIDER_MODELS["groq"]["standard"])
        return GroqAdapter(model=model)

    @classmethod
    def _create_gemini(cls) -> LLMPort:
        api_key = os.getenv("GEMINI_API_KEY")
        model = os.getenv("GEMINI_MODEL", cls.PROVIDER_MODELS["gemini"]["standard"])
        return GeminiAdapter(api_key=api_key, model=model)

    @classmethod
    def _create_ollama(cls) -> LLMPort:
        base_url = os.getenv("OLLAMA_BASE_URL")
        model = os.getenv("OLLAMA_MODEL", cls.PROVIDER_MODELS["ollama"]["standard"])
        return OllamaAdapter(base_url=base_url, model=model)

    @classmethod
    def create_standard(cls, provider: str = None) -> LLMPort:
        """Create standard model adapter"""
        provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
        model = cls.PROVIDER_MODELS.get(provider, {}).get("standard")
        
        creators = {
            "groq": lambda: GroqAdapter(model=model),
            "gemini": lambda: GeminiAdapter(model=model),
            "ollama": lambda: OllamaAdapter(model=model),
        }
        
        creator = creators.get(provider, creators["ollama"])
        return creator()

    @classmethod
    def create_premium(cls, provider: str = None) -> LLMPort:
        """Create premium model adapter for critical tasks"""
        provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
        model = cls.PROVIDER_MODELS.get(provider, {}).get("premium")
        
        creators = {
            "groq": lambda: GroqAdapter(model=model),
            "gemini": lambda: GeminiAdapter(model=model),
            "ollama": lambda: OllamaAdapter(model=model),
        }
        
        creator = creators.get(provider, creators["ollama"])
        return creator()

    @classmethod
    def get_available_providers(cls) -> list[dict]:
        """Get list of available providers with their status"""
        providers = []
        
        groq = GroqAdapter()
        providers.append({
            "name": "groq",
            "available": groq.is_available(),
            "models": ["llama-3.3-70b-versatile"],
            "cost": "Free tier available"
        })
        
        gemini = GeminiAdapter()
        providers.append({
            "name": "gemini",
            "available": gemini.is_available(),
            "models": ["gemini-1.5-flash", "gemini-1.5-pro"],
            "cost": "Free tier available"
        })
        
        ollama = OllamaAdapter()
        providers.append({
            "name": "ollama",
            "available": ollama.is_available(),
            "models": ["llama3.2", "mistral", "codellama"],
            "cost": "Free (local)"
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
