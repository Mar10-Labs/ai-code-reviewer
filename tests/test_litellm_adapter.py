import pytest
import os
from unittest.mock import patch, MagicMock

from src.llm.adapters.litellm_adapter import LiteLLMAdapter, create_litellm_adapter
from src.llm.ports.llm_port import LLMConfig, LLMResponse


class TestLiteLLMAdapter:
    def test_default_provider(self):
        adapter = LiteLLMAdapter()
        assert adapter.provider == "groq"

    def test_custom_provider(self):
        adapter = LiteLLMAdapter(provider="gemini")
        assert adapter.provider == "gemini"

    def test_provider_name(self):
        adapter = LiteLLMAdapter(provider="openai")
        assert adapter.get_provider_name() == "litellm-openai"

    def test_model_mapping_groq(self):
        adapter = LiteLLMAdapter(provider="groq")
        assert "groq" in adapter.model

    def test_custom_model(self):
        adapter = LiteLLMAdapter(provider="gemini", model="gemini-1.5-pro")
        assert adapter.model == "gemini/gemini-1.5-pro"

    def test_custom_model_with_provider_prefix(self):
        adapter = LiteLLMAdapter(provider="openai", model="openai/gpt-4")
        assert adapter.model == "openai/gpt-4"

    def test_api_key_from_env(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}):
            adapter = LiteLLMAdapter(provider="gemini")
            assert adapter.api_key == "test-key-123"

    def test_base_url_from_env(self):
        with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://custom:8080"}):
            adapter = LiteLLMAdapter()
            assert adapter.base_url == "http://custom:8080"

    def test_is_available_with_api_key(self):
        adapter = LiteLLMAdapter(api_key="test-key")
        assert adapter.is_available() is True

    def test_is_available_ollama_no_base_url(self):
        adapter = LiteLLMAdapter(provider="ollama")
        with patch.object(adapter, '_check_ollama', return_value=False):
            assert adapter.is_available() is False


class TestCreateLiteLLMAdapter:
    def test_create_with_defaults(self):
        adapter = create_litellm_adapter()
        assert adapter is not None
        assert isinstance(adapter, LiteLLMAdapter)

    def test_create_with_custom_provider(self):
        adapter = create_litellm_adapter(provider="openai", model="gpt-4")
        assert adapter.provider == "openai"
        assert "gpt-4" in adapter.model

    def test_create_with_api_key(self):
        adapter = create_litellm_adapter(api_key="secret-key")
        assert adapter.api_key == "secret-key"


class TestLiteLLMProviderModels:
    def test_supported_providers(self):
        supported = ["groq", "gemini", "openai", "anthropic", "ollama", "huggingface"]
        for provider in supported:
            adapter = LiteLLMAdapter(provider=provider)
            assert adapter.provider == provider

    def test_model_format(self):
        adapter = LiteLLMAdapter(provider="huggingface", model="mistral-7b")
        assert "/" in adapter.model
        assert adapter.model.startswith("huggingface/")
