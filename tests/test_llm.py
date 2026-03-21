import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.llm.ports.llm_port import LLMPort, LLMResponse, LLMConfig
from src.llm.factory import LLMFactory, get_llm, get_standard_llm, get_premium_llm
from src.llm.adapters.llm_adapter import LLMAdapter


class TestLLMConfig:
    def test_default_config(self):
        config = LLMConfig(model="test-model")
        assert config.model == "test-model"
        assert config.temperature == 0.7
        assert config.max_tokens == 2048
        assert config.timeout == 60

    def test_custom_config(self):
        config = LLMConfig(
            model="custom-model",
            temperature=0.5,
            max_tokens=1000,
            timeout=30
        )
        assert config.temperature == 0.5
        assert config.max_tokens == 1000
        assert config.timeout == 30


class TestLLMResponse:
    def test_response_creation(self):
        response = LLMResponse(
            content="Hello, world!",
            model="test-model",
            provider="test",
            tokens_used=5,
            cost_usd=0.01,
            latency_ms=100.0
        )
        assert response.content == "Hello, world!"
        assert response.provider == "test"
        assert response.tokens_used == 5

    def test_response_optional_fields(self):
        response = LLMResponse(
            content="Test",
            model="model",
            provider="provider"
        )
        assert response.tokens_used is None
        assert response.cost_usd is None
        assert response.latency_ms is None


class TestLLMAdapter:
    def test_provider_name_groq(self):
        adapter = LLMAdapter(provider="groq", api_key="test-key")
        assert adapter.get_provider_name() == "groq"

    def test_provider_name_gemini(self):
        adapter = LLMAdapter(provider="gemini", api_key="test-key")
        assert adapter.get_provider_name() == "gemini"

    def test_provider_name_ollama(self):
        adapter = LLMAdapter(provider="ollama", api_key="test-key")
        assert adapter.get_provider_name() == "ollama"

    def test_is_available_with_key(self):
        adapter = LLMAdapter(provider="groq", api_key="test-key")
        assert adapter.is_available() is True

    def test_is_available_without_key(self):
        adapter = LLMAdapter(provider="groq", api_key=None)
        assert adapter.is_available() is False

    def test_default_model_groq(self):
        adapter = LLMAdapter(provider="groq", api_key="test")
        assert adapter.model == "llama-3.3-70b-versatile"

    def test_default_model_gemini(self):
        adapter = LLMAdapter(provider="gemini", api_key="test")
        assert adapter.model == "gemini-1.5-flash"

    def test_custom_model(self):
        adapter = LLMAdapter(provider="groq", api_key="test", model="custom-model")
        assert adapter.model == "custom-model"

    def test_base_url_groq(self):
        adapter = LLMAdapter(provider="groq", api_key="test")
        assert "api.groq.com" in adapter.base_url

    def test_base_url_gemini(self):
        adapter = LLMAdapter(provider="gemini", api_key="test")
        assert "generativelanguage.googleapis.com" in adapter.base_url

    @pytest.mark.asyncio
    async def test_complete_requires_api_key(self):
        adapter = LLMAdapter(provider="groq", api_key=None)
        with pytest.raises(RuntimeError, match="not configured"):
            await adapter.complete("test prompt")


class TestLLMFactory:
    def test_create_groq(self):
        with patch.dict("os.environ", {"LLM_API_KEY": "test-key"}, clear=True):
            adapter = LLMFactory.create("groq")
            assert isinstance(adapter, LLMAdapter)
            assert adapter.provider == "groq"

    def test_create_gemini(self):
        with patch.dict("os.environ", {"LLM_API_KEY": "test-key"}, clear=True):
            adapter = LLMFactory.create("gemini")
            assert isinstance(adapter, LLMAdapter)
            assert adapter.provider == "gemini"

    def test_create_ollama(self):
        adapter = LLMFactory.create("ollama")
        assert isinstance(adapter, LLMAdapter)
        assert adapter.provider == "ollama"

    def test_create_standard_sets_model(self):
        with patch.dict("os.environ", {"LLM_API_KEY": "test"}, clear=True):
            adapter = LLMFactory.create_standard("groq")
            assert adapter.model == "llama-3.3-70b-versatile"

    def test_create_premium_sets_model(self):
        with patch.dict("os.environ", {"LLM_API_KEY": "test"}, clear=True):
            adapter = LLMFactory.create_premium("groq")
            assert adapter.model == "llama-3.3-70b-versatile"

    def test_get_available_providers(self):
        providers = LLMFactory.get_available_providers()
        assert len(providers) == 4
        names = [p["name"] for p in providers]
        assert "groq" in names
        assert "gemini" in names
        assert "ollama" in names
        assert "openai" in names


class TestConvenienceFunctions:
    def test_get_llm_returns_port(self):
        adapter = get_llm()
        assert isinstance(adapter, LLMPort)

    def test_get_standard_llm_returns_port(self):
        adapter = get_standard_llm()
        assert isinstance(adapter, LLMPort)

    def test_get_premium_llm_returns_port(self):
        adapter = get_premium_llm()
        assert isinstance(adapter, LLMPort)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
