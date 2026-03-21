import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

from src.llm.factory import LLMFactory
from src.llm.ports.llm_port import LLMResponse, LLMConfig
from src.llm.adapters.llm_adapter import LLMAdapter


def create_mock_response(status=200, data=None):
    mock_response = MagicMock()
    mock_response.status_code = status
    mock_response.json.return_value = data or {}
    return mock_response


class TestLLMAdapterGroqIntegration:
    @pytest.mark.asyncio
    async def test_complete_with_mock(self):
        adapter = LLMAdapter(provider="groq", api_key="test-key")
        
        mock_response = create_mock_response(200, {
            "choices": [{"message": {"content": "Test response"}}],
            "model": "llama-3.3-70b-versatile",
            "usage": {"total_tokens": 10}
        })
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance
            
            response = await adapter.complete("Hello")
            
            assert response.content == "Test response"
            assert response.provider == "groq"
            assert response.tokens_used == 10

    @pytest.mark.asyncio
    async def test_complete_structured_with_mock(self):
        adapter = LLMAdapter(provider="groq", api_key="test-key")
        
        mock_response = create_mock_response(200, {
            "choices": [{
                "message": {
                    "content": '{"file_path": "test.py", "severity": "warning"}'
                }
            }],
            "model": "llama-3.3-70b-versatile",
            "usage": {"total_tokens": 50}
        })
        
        schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "severity": {"type": "string"}
            }
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance
            
            response = await adapter.complete_structured("Review this", schema)
            
            assert response.provider == "groq"
            data = json.loads(response.content)
            assert data["file_path"] == "test.py"

    @pytest.mark.asyncio
    async def test_complete_handles_error(self):
        adapter = LLMAdapter(provider="groq", api_key="test-key")
        
        mock_response = create_mock_response(401, {})
        mock_response.text = "Unauthorized"
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance
            
            with pytest.raises(RuntimeError, match="401"):
                await adapter.complete("Hello")


class TestLLMAdapterGeminiIntegration:
    @pytest.mark.asyncio
    async def test_complete_with_mock(self):
        adapter = LLMAdapter(provider="gemini", api_key="test-key", model="gemini-1.5-flash")
        
        mock_response = create_mock_response(200, {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Gemini response"}]
                }
            }]
        })
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance
            
            response = await adapter.complete("Hello")
            
            assert response.content == "Gemini response"
            assert response.provider == "gemini"


class TestLLMAdapterOllamaIntegration:
    @pytest.mark.asyncio
    async def test_complete_with_mock(self):
        adapter = LLMAdapter(provider="ollama", api_key="ollama")
        
        mock_response = create_mock_response(200, {
            "choices": [{"message": {"content": "Ollama response"}}],
            "usage": {"total_tokens": 5}
        })
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_instance
            
            response = await adapter.complete("Hello")
            
            assert response.content == "Ollama response"
            assert response.provider == "ollama"


class TestLLMFactoryIntegration:
    def test_factory_creates_llm_adapter(self):
        adapter = LLMFactory.create("groq")
        assert isinstance(adapter, LLMAdapter)
        assert adapter.provider == "groq"

    def test_factory_creates_groq_with_api_key(self):
        with patch.dict("os.environ", {"LLM_API_KEY": "test"}, clear=True):
            adapter = LLMFactory.create("groq")
            assert isinstance(adapter, LLMAdapter)
            assert adapter.api_key == "test"
            assert adapter.provider == "groq"

    def test_factory_creates_gemini_with_api_key(self):
        with patch.dict("os.environ", {"LLM_API_KEY": "test"}, clear=True):
            adapter = LLMFactory.create("gemini")
            assert isinstance(adapter, LLMAdapter)
            assert adapter.api_key == "test"
            assert adapter.provider == "gemini"

    def test_factory_creates_ollama(self):
        adapter = LLMFactory.create("ollama")
        assert isinstance(adapter, LLMAdapter)
        assert adapter.provider == "ollama"

    def test_factory_standard_model_selection(self):
        with patch.dict("os.environ", {"LLM_API_KEY": "test"}, clear=True):
            standard = LLMFactory.create_standard("groq")
            premium = LLMFactory.create_premium("groq")
            
            assert standard.model == "llama-3.3-70b-versatile"
            assert premium.model == "llama-3.3-70b-versatile"


class TestLLMPortContract:
    def test_llm_adapter_implements_port_interface(self):
        adapter = LLMAdapter(provider="groq", api_key="test")
        
        assert hasattr(adapter, "complete")
        assert hasattr(adapter, "complete_structured")
        assert hasattr(adapter, "is_available")
        assert hasattr(adapter, "get_provider_name")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
