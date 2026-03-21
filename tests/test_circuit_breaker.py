import pytest
import asyncio
from src.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitState
)


class TestCircuitBreaker:
    """Tests para Circuit Breaker"""
    
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed
    
    def test_successful_call_does_not_open(self):
        cb = CircuitBreaker(name="test", config=CircuitBreakerConfig(failure_threshold=3))
        
        async def success_func():
            return "success"
        
        for _ in range(5):
            result = asyncio.run(cb.call(success_func))
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
    
    def test_failure_count_opens_circuit(self):
        cb = CircuitBreaker(
            name="test", 
            config=CircuitBreakerConfig(failure_threshold=3, timeout=60)
        )
        
        def failing_func():
            raise ValueError("Test error")
        
        success_count = 0
        for i in range(5):
            try:
                cb.call_sync(failing_func)
            except ValueError:
                success_count += 1
            except CircuitBreakerOpen:
                break
        
        assert success_count == 3
        assert cb.state == CircuitState.OPEN
    
    def test_open_circuit_rejects_calls(self):
        cb = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(failure_threshold=1, timeout=60)
        )
        
        def fail_once():
            raise ValueError("Fail")
        
        try:
            cb.call_sync(fail_once)
        except ValueError:
            pass
        
        with pytest.raises(CircuitBreakerOpen):
            cb.call_sync(fail_once)
    
    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(failure_threshold=1, timeout=0.1)
        )
        
        def fail():
            raise ValueError("Fail")
        
        try:
            cb.call_sync(fail)
        except ValueError:
            pass
        
        assert cb.state == CircuitState.OPEN
        
        import time
        time.sleep(0.2)
        
        result = None
        try:
            result = cb.call_sync(lambda: "success")
        except CircuitBreakerOpen:
            pass
        
        assert result == "success"
        assert cb.state == CircuitState.HALF_OPEN
    
    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(
                failure_threshold=1, 
                timeout=0.1,
                success_threshold=2
            )
        )
        
        def fail():
            raise ValueError("Fail")
        
        try:
            cb.call_sync(fail)
        except ValueError:
            pass
        
        import time
        time.sleep(0.2)
        
        for i in range(3):
            try:
                cb.call_sync(lambda: f"success_{i}")
            except CircuitBreakerOpen:
                break
        
        assert cb.state == CircuitState.CLOSED
    
    def test_get_status(self):
        cb = CircuitBreaker(name="test_status")
        status = cb.get_status()
        
        assert status["name"] == "test_status"
        assert status["state"] == "closed"
        assert "stats" in status
    
    def test_reset(self):
        cb = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(failure_threshold=1)
        )
        
        def fail():
            raise ValueError("Fail")
        
        try:
            cb.call_sync(fail)
        except ValueError:
            pass
        
        cb.reset()
        
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestCircuitBreakerDecorator:
    """Tests para el decorador de Circuit Breaker"""
    
    def test_decorator_creates_circuit_breaker(self):
        @CircuitBreaker.decorator(failure_threshold=3, name="decorated")
        async def my_func():
            return "done"
        
        assert hasattr(my_func, 'circuit_breaker')
        assert my_func.circuit_breaker.name == "decorated"


class TestLLMCircuitBreakerAdapter:
    """Tests para el adapter de LLM con Circuit Breaker"""
    
    @pytest.mark.asyncio
    async def test_successful_call(self):
        from src.llm.adapters.groq_adapter import GroqAdapter
        from src.llm.adapters.circuit_breaker_adapter import LLMCircuitBreakerAdapter
        
        mock_adapter = GroqAdapter(api_key="test-key")
        
        original_complete = mock_adapter.complete
        
        async def mock_complete(prompt, config=None):
            return await original_complete(prompt, config) if mock_adapter.is_available() else None
        
        mock_adapter.complete = mock_complete
        mock_adapter.is_available = lambda: True
        
        cb_adapter = LLMCircuitBreakerAdapter(mock_adapter)
        assert cb_adapter.get_provider_name() == "groq_protected"
    
    def test_status(self):
        from src.llm.adapters.groq_adapter import GroqAdapter
        from src.llm.adapters.circuit_breaker_adapter import LLMCircuitBreakerAdapter
        
        adapter = GroqAdapter(api_key="test")
        cb_adapter = LLMCircuitBreakerAdapter(adapter)
        
        status = cb_adapter.get_status()
        assert "name" in status
        assert "state" in status
