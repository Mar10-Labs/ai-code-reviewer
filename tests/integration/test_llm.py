import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

from src.llm.factory import LLMFactory
from src.llm.ports.llm_port import LLMResponse, LLMConfig
from src.llm.adapters.groq_adapter import GroqAdapter
from src.llm.adapters.gemini_adapter import GeminiAdapter
from src.llm.adapters.ollama_adapter import OllamaAdapter


class TestGroqIntegration:
    @pytest.mark.asyncio
    async def test_complete_with_mock(self):
        adapter = GroqAdapter(api_key="test-key")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "model": "llama-3.3-70b-versatile",
            "usage": {"total_tokens": 10}
        }
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            response = await adapter.complete("Hello")
            
            assert response.content == "Test response"
            assert response.provider == "groq"
            assert response.tokens_used == 10

    @pytest.mark.asyncio
    async def test_complete_structured_with_mock(self):
        adapter = GroqAdapter(api_key="test-key")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"file_path": "test.py", "severity": "warning"}'
                }
            }],
            "model": "llama-3.3-70b-versatile",
            "usage": {"total_tokens": 50}
        }
        
        schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "severity": {"type": "string"}
            }
        }
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            response = await adapter.complete_structured("Review this", schema)
            
            assert response.provider == "groq"
            data = json.loads(response.content)
            assert data["file_path"] == "test.py"

    @pytest.mark.asyncio
    async def test_complete_handles_error(self):
        adapter = GroqAdapter(api_key="test-key")
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            with pytest.raises(RuntimeError, match="401"):
                await adapter.complete("Hello")


class TestOllamaIntegration:
    @pytest.mark.asyncio
    async def test_complete_with_mock(self):
        adapter = OllamaAdapter(base_url="http://localhost:11434", model="llama3.2")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Ollama response",
            "eval_count": 5
        }
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            response = await adapter.complete("Hello")
            
            assert response.content == "Ollama response"
            assert response.provider == "ollama"
            assert response.tokens_used == 5

    def test_is_available_check(self):
        adapter = OllamaAdapter()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.get", return_value=mock_response):
            assert adapter.is_available() is True


class TestGeminiIntegration:
    @pytest.mark.asyncio
    async def test_complete_with_mock(self):
        adapter = GeminiAdapter(api_key="test-key", model="gemini-1.5-flash")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Gemini response"}]
                }
            }]
        }
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            response = await adapter.complete("Hello")
            
            assert response.content == "Gemini response"
            assert response.provider == "gemini"


class TestLLMFactoryIntegration:
    def test_factory_creates_ollama_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            adapter = LLMFactory.create("ollama")
            assert isinstance(adapter, OllamaAdapter)

    def test_factory_creates_groq_with_api_key(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": "test"}, clear=True):
            adapter = LLMFactory.create("groq")
            assert isinstance(adapter, GroqAdapter)
            assert adapter.api_key == "test"

    def test_factory_creates_gemini_with_api_key(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test"}, clear=True):
            adapter = LLMFactory.create("gemini")
            assert isinstance(adapter, GeminiAdapter)
            assert adapter.api_key == "test"

    def test_factory_standard_model_selection(self):
        with patch.dict("os.environ", {}, clear=True):
            standard = LLMFactory.create_standard("ollama")
            premium = LLMFactory.create_premium("ollama")
            
            assert standard.model == "llama3.2"
            assert premium.model == "llama3.2"


class TestLLMPortContract:
    def test_all_adapters_implement_port_interface(self):
        adapters = [
            GroqAdapter(api_key="test"),
            GeminiAdapter(api_key="test"),
            OllamaAdapter(),
        ]
        
        for adapter in adapters:
            assert hasattr(adapter, "complete")
            assert hasattr(adapter, "complete_structured")
            assert hasattr(adapter, "is_available")
            assert hasattr(adapter, "get_provider_name")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
