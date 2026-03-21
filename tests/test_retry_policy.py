import pytest
import asyncio
import time
from unittest.mock import AsyncMock

from src.infrastructure.resilience.retry_policy import (
    retry_with_backoff,
    retry_decorator,
    RetryPolicy,
    RetryConfig,
    RetryStrategy,
    RetryExhausted,
    RetryContext,
    calculate_delay,
    AsyncRetryHelper
)


class TestCalculateDelay:
    """Tests para calculate_delay"""
    
    def test_exponential_delay(self):
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=1.0,
            max_delay=60.0,
            jitter=False
        )
        
        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 4.0
        assert calculate_delay(3, config) == 8.0
    
    def test_linear_delay(self):
        config = RetryConfig(
            strategy=RetryStrategy.LINEAR,
            base_delay=1.0,
            jitter=False
        )
        
        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 3.0
    
    def test_fixed_delay(self):
        config = RetryConfig(
            strategy=RetryStrategy.FIXED,
            base_delay=2.0,
            jitter=False
        )
        
        assert calculate_delay(0, config) == 2.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 2.0
    
    def test_max_delay_respected(self):
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=10.0,
            max_delay=30.0,
            jitter=False
        )
        
        assert calculate_delay(10, config) == 30.0


class TestRetryWithBackoff:
    """Tests para retry_with_backoff"""
    
    @pytest.mark.asyncio
    async def test_succeeds_first_attempt(self):
        async def success_func():
            return "success"
        
        result = await retry_with_backoff(success_func)
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = await retry_with_backoff(
            flaky_func,
            RetryConfig(max_retries=5, base_delay=0.01)
        )
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_raises_when_exhausted(self):
        async def always_fail():
            raise ValueError("Always fails")
        
        with pytest.raises(RetryExhausted) as exc_info:
            await retry_with_backoff(
                always_fail,
                RetryConfig(max_retries=3, base_delay=0.01)
            )
        
        assert exc_info.value.attempts == 3
    
    @pytest.mark.asyncio
    async def test_with_args(self):
        async def func_with_args(a, b, c=0):
            return a + b + c
        
        result = await retry_with_backoff(func_with_args, None, 1, 2, c=3)
        
        assert result == 6


class TestRetryDecorator:
    """Tests para retry_decorator"""
    
    @pytest.mark.asyncio
    async def test_decorator_success(self):
        @retry_decorator(RetryConfig(max_retries=3))
        async def my_func():
            return "done"
        
        result = await my_func()
        
        assert result == "done"
    
    @pytest.mark.asyncio
    async def test_decorator_with_retry(self):
        call_count = 0
        
        @retry_decorator(RetryConfig(max_retries=3, base_delay=0.01))
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Flaky")
            return "done"
        
        result = await flaky()
        
        assert result == "done"
        assert call_count == 2


class TestRetryPolicy:
    """Tests para RetryPolicy"""
    
    @pytest.mark.asyncio
    async def test_basic_retry(self):
        policy = RetryPolicy(RetryConfig(max_retries=3, base_delay=0.01))
        
        call_count = 0
        
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Flaky")
            return "success"
        
        result = await policy.execute(flaky)
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        policy = RetryPolicy(RetryConfig(max_retries=3, base_delay=0.01))
        
        retry_contexts = []
        policy.on_retry(lambda ctx: retry_contexts.append(ctx))
        
        call_count = 0
        
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Flaky")
            return "success"
        
        await policy.execute(flaky)
        
        assert len(retry_contexts) == 2
        assert retry_contexts[0].attempt == 0
        assert retry_contexts[1].attempt == 1
    
    @pytest.mark.asyncio
    async def test_on_success_callback(self):
        policy = RetryPolicy(RetryConfig(max_retries=3))
        
        success_called = []
        policy.on_success(lambda: success_called.append(True))
        
        async def success():
            return "done"
        
        await policy.execute(success)
        
        assert len(success_called) == 1
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        policy = RetryPolicy(RetryConfig(max_retries=3))
        
        async def success():
            return "done"
        
        await policy.execute(success)
        
        stats = policy.get_stats()
        
        assert stats["stats"]["successful_attempts"] == 1
        assert stats["config"]["max_retries"] == 3


class TestRetryContext:
    """Tests para RetryContext"""
    
    def test_will_retry(self):
        ctx = RetryContext(attempt=0, max_attempts=3, delay=1.0)
        
        assert ctx.will_retry is True
        assert ctx.is_last_attempt is False
    
    def test_is_last_attempt(self):
        ctx = RetryContext(attempt=2, max_attempts=3, delay=1.0)
        
        assert ctx.will_retry is False
        assert ctx.is_last_attempt is True
    
    def test_will_retry_true_before_last(self):
        ctx = RetryContext(attempt=3, max_attempts=5, delay=1.0)
        
        assert ctx.will_retry is True
        assert ctx.is_last_attempt is False


class TestAsyncRetryHelper:
    """Tests para AsyncRetryHelper"""
    
    @pytest.mark.asyncio
    async def test_execute_all(self):
        helper = AsyncRetryHelper(RetryConfig(max_retries=2, base_delay=0.01))
        
        async def func1():
            return "result1"
        
        async def func2():
            return "result2"
        
        results = await helper.execute_all([
            (func1, {}),
            (func2, {})
        ])
        
        assert results[0] == "result1"
        assert results[1] == "result2"
    
    @pytest.mark.asyncio
    async def test_execute_first_success(self):
        helper = AsyncRetryHelper(RetryConfig(max_retries=1, base_delay=0.01))
        
        async def slow_fail():
            await asyncio.sleep(0.5)
            raise ValueError("Fail")
        
        async def fast_success():
            return "winner"
        
        result = await helper.execute_first_success([
            (fast_success, {}),
            (slow_fail, {}),
        ], timeout=5.0)
        
        assert result == "winner"
