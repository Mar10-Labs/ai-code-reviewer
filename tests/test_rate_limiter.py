import pytest
import asyncio
import time

from src.infrastructure.resilience.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    MultiRateLimiter,
    get_github_limiter
)


class TestRateLimiter:
    """Tests para RateLimiter"""
    
    @pytest.mark.asyncio
    async def test_acquire_basic(self):
        limiter = RateLimiter(
            config=RateLimitConfig(requests_per_second=10, burst_size=5)
        )
        
        result = await limiter.acquire()
        
        assert result is True
        stats = limiter.get_stats()
        assert stats["stats"]["allowed_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_acquire_multiple(self):
        limiter = RateLimiter(
            config=RateLimitConfig(requests_per_second=10, burst_size=10)
        )
        
        for _ in range(5):
            await limiter.acquire()
        
        stats = limiter.get_stats()
        assert stats["stats"]["allowed_requests"] == 5
    
    @pytest.mark.asyncio
    async def test_burst_limit(self):
        limiter = RateLimiter(
            config=RateLimitConfig(requests_per_second=1, burst_size=3)
        )
        
        for _ in range(3):
            await limiter.acquire()
        
        start = time.time()
        try:
            await limiter.acquire()
        except Exception:
            pass
        elapsed = time.time() - start
        
        assert elapsed >= 0.9
    
    @pytest.mark.asyncio
    async def test_try_acquire(self):
        limiter = RateLimiter(
            config=RateLimitConfig(requests_per_second=10, burst_size=2)
        )
        
        result1 = await limiter.try_acquire()
        result2 = await limiter.try_acquire()
        result3 = await limiter.try_acquire()
        
        assert result1 is True
        assert result2 is True
        assert result3 is False
    
    @pytest.mark.asyncio
    async def test_hourly_limit(self):
        limiter = RateLimiter(
            config=RateLimitConfig(requests_per_hour=3, burst_size=10)
        )
        
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        
        with pytest.raises(RateLimitExceeded):
            await limiter.acquire()
    
    @pytest.mark.asyncio
    async def test_execute_function(self):
        limiter = RateLimiter(
            config=RateLimitConfig(requests_per_second=10, burst_size=5)
        )
        
        async def my_func():
            return "result"
        
        result = await limiter.execute(my_func)
        
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_get_wait_time(self):
        limiter = RateLimiter(
            config=RateLimitConfig(requests_per_second=10, burst_size=2)
        )
        
        await limiter.acquire()
        await limiter.acquire()
        
        wait_time = limiter.get_wait_time()
        
        assert wait_time > 0
    
    @pytest.mark.asyncio
    async def test_reset(self):
        limiter = RateLimiter(
            config=RateLimitConfig(requests_per_second=10, burst_size=5)
        )
        
        await limiter.acquire()
        limiter.reset()
        
        stats = limiter.get_stats()
        assert stats["tokens_available"] == 5


class TestMultiRateLimiter:
    """Tests para MultiRateLimiter"""
    
    @pytest.mark.asyncio
    async def test_add_and_acquire(self):
        limiter = MultiRateLimiter()
        limiter.add_limit("api", requests_per_hour=1000)
        
        await limiter.acquire("api")
        
        stats = limiter.get_stats("api")
        assert stats["stats"]["allowed_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_multiple_limits(self):
        limiter = MultiRateLimiter()
        limiter.add_limit("api1", requests_per_hour=1000)
        limiter.add_limit("api2", requests_per_hour=500)
        
        await limiter.acquire("api1")
        await limiter.acquire("api2")
        
        stats = limiter.get_stats()
        assert "api1" in stats
        assert "api2" in stats
    
    @pytest.mark.asyncio
    async def test_unknown_limit_raises(self):
        limiter = MultiRateLimiter()
        
        with pytest.raises(ValueError):
            await limiter.acquire("unknown")
    
    @pytest.mark.asyncio
    async def test_try_acquire(self):
        limiter = MultiRateLimiter()
        limiter.add_limit("api", requests_per_hour=1, burst_size=1)
        
        result1 = await limiter.try_acquire("api")
        result2 = await limiter.try_acquire("api")
        
        assert result1 is True
        assert result2 is False


class TestGetGitHubLimiter:
    """Tests para get_github_limiter"""
    
    def test_returns_multi_limiter(self):
        limiter = get_github_limiter()
        
        assert isinstance(limiter, MultiRateLimiter)
    
    def test_has_github_limits(self):
        limiter = get_github_limiter()
        stats = limiter.get_stats()
        
        assert "github_api" in stats
        assert "github_comments" in stats
        assert "github_reviews" in stats
    
    @pytest.mark.asyncio
    async def test_can_acquire_github_api(self):
        limiter = get_github_limiter()
        
        await limiter.acquire("github_api")
        
        stats = limiter.get_stats("github_api")
        assert stats["stats"]["allowed_requests"] >= 1
