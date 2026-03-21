import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.llm.fallback_chain import (
    LLMFallbackChain,
    FallbackConfig,
    FallbackReason,
    FallbackResponse,
    DefaultLLMChain
)
from src.llm.ports.llm_port import LLMResponse


class MockLLMAdapter:
    def __init__(self, name: str = "mock", available: bool = True, should_fail: bool = False):
        self._name = name
        self._available = available
        self._should_fail = should_fail
        self.call_count = 0
    
    def get_provider_name(self) -> str:
        return self._name
    
    def is_available(self) -> bool:
        return self._available
    
    async def complete(self, prompt: str, config=None) -> LLMResponse:
        self.call_count += 1
        if self._should_fail:
            raise Exception(f"{self._name} failed")
        return LLMResponse(
            content=f"Response from {self._name}",
            model=self._name,
            provider=self._name
        )
    
    async def complete_structured(self, prompt: str, schema: dict, config=None) -> LLMResponse:
        return await self.complete(prompt, config)


class TestLLMFallbackChain:
    """Tests para LLM Fallback Chain"""
    
    @pytest.mark.asyncio
    async def test_first_provider_works(self):
        chain = LLMFallbackChain()
        chain.add_provider(MockLLMAdapter(name="provider1"), name="provider1")
        
        response = await chain.complete("test prompt")
        
        assert response.content == "Response from provider1"
        assert response.provider == "provider1"
    
    @pytest.mark.asyncio
    async def test_fallback_to_second_provider(self):
        chain = LLMFallbackChain()
        chain.add_provider(MockLLMAdapter(name="p1", should_fail=True), name="p1")
        chain.add_provider(MockLLMAdapter(name="p2"), name="p2")
        
        response = await chain.complete("test prompt")
        
        assert response.content == "Response from p2"
        assert response.provider == "p2"
    
    @pytest.mark.asyncio
    async def test_fallback_to_third_provider(self):
        chain = LLMFallbackChain()
        chain.add_provider(MockLLMAdapter(name="p1", should_fail=True), name="p1")
        chain.add_provider(MockLLMAdapter(name="p2", should_fail=True), name="p2")
        chain.add_provider(MockLLMAdapter(name="p3"), name="p3")
        
        response = await chain.complete("test prompt")
        
        assert response.content == "Response from p3"
        assert response.provider == "p3"
    
    @pytest.mark.asyncio
    async def test_all_fail_uses_fallback(self):
        chain = LLMFallbackChain()
        chain.add_provider(MockLLMAdapter(name="p1", should_fail=True), name="p1")
        chain.add_provider(MockLLMAdapter(name="p2", should_fail=True), name="p2")
        
        def custom_fallback():
            return FallbackResponse(
                content="Custom fallback message",
                model="fallback",
                provider="custom"
            )
        
        chain.set_fallback(custom_fallback)
        
        response = await chain.complete("test prompt")
        
        assert response.content == "Custom fallback message"
        assert response.is_fallback is True
    
    @pytest.mark.asyncio
    async def test_unavailable_provider_skipped(self):
        chain = LLMFallbackChain()
        chain.add_provider(MockLLMAdapter(name="p1", available=False), name="p1")
        chain.add_provider(MockLLMAdapter(name="p2"), name="p2")
        
        response = await chain.complete("test prompt")
        
        assert response.content == "Response from p2"
    
    @pytest.mark.asyncio
    async def test_no_fallback_returns_default(self):
        chain = LLMFallbackChain()
        chain.add_provider(MockLLMAdapter(name="p1", should_fail=True), name="p1")
        
        response = await chain.complete("test prompt")
        
        assert response.is_fallback is True
        assert response.content is not None
    
    @pytest.mark.asyncio
    async def test_providers_tried_tracked(self):
        chain = LLMFallbackChain()
        chain.add_provider(MockLLMAdapter(name="p1", should_fail=True), name="p1")
        chain.add_provider(MockLLMAdapter(name="p2"), name="p2")
        
        response = await chain.complete("test prompt")
        
        assert response.providers_tried == ["p1", "p2"]
    
    @pytest.mark.asyncio
    async def test_complete_structured(self):
        chain = LLMFallbackChain()
        chain.add_provider(MockLLMAdapter(name="p1"), name="p1")
        
        response = await chain.complete_structured(
            "test prompt", 
            {"type": "object"}
        )
        
        assert response.content == "Response from p1"
    
    @pytest.mark.asyncio
    async def test_get_provider_status(self):
        chain = LLMFallbackChain()
        chain.add_provider(MockLLMAdapter(name="p1"), name="p1")
        chain.add_provider(MockLLMAdapter(name="p2", available=False), name="p2")
        
        status = chain.get_provider_status()
        
        assert len(status) == 2
        assert status[0]["name"] == "p1"
        assert status[0]["available"] is True
        assert status[1]["available"] is False


class TestDefaultLLMChain:
    """Tests para DefaultLLMChain"""
    
    @pytest.mark.asyncio
    async def test_default_chain_initializes(self):
        chain = DefaultLLMChain()
        
        status = chain.get_provider_status()
        
        assert len(status) >= 1
    
    @pytest.mark.asyncio
    async def test_complete_returns_response(self):
        chain = DefaultLLMChain()
        
        response = await chain.complete("test")
        
        assert response is not None
        assert hasattr(response, 'content')


class TestFallbackResponse:
    """Tests para FallbackResponse"""
    
    def test_fallback_response_creation(self):
        response = FallbackResponse(
            content="Test",
            model="test",
            provider="test",
            is_fallback=True,
            fallback_reason="test_reason",
            providers_tried=["p1", "p2"]
        )
        
        assert response.is_fallback is True
        assert response.fallback_reason == "test_reason"
        assert response.providers_tried == ["p1", "p2"]
