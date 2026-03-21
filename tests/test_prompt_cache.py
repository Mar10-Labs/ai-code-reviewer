import pytest
from datetime import datetime, timezone, timedelta
from src.infrastructure.services.prompt_cache import (
    PromptCache,
    PromptCacheConfig,
    CachedPrompt,
    CacheStats,
)


class TestPromptCacheConfig:
    def test_default_config(self):
        config = PromptCacheConfig()
        assert config.ttl_seconds == 3600
        assert config.max_size == 100
        assert config.enabled is True

    def test_custom_config(self):
        config = PromptCacheConfig(ttl_seconds=7200, max_size=50, enabled=False)
        assert config.ttl_seconds == 7200
        assert config.max_size == 50
        assert config.enabled is False


class TestCacheStats:
    def test_initial_stats(self):
        stats = CacheStats()
        assert stats.total_requests == 0
        assert stats.cache_hits == 0
        assert stats.cache_misses == 0
        assert stats.tokens_saved == 0
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        stats = CacheStats(total_requests=10, cache_hits=3, cache_misses=7)
        assert stats.hit_rate == 0.3

    def test_savings_percent(self):
        stats = CacheStats(total_requests=100, cache_hits=75, cache_misses=25)
        assert stats.savings_percent == 75.0


class TestCachedPrompt:
    def test_cached_prompt_creation(self):
        now = datetime.now(timezone.utc)
        prompt = CachedPrompt(
            content="test prompt",
            hash="abc123",
            created_at=now,
            last_used=now,
            tokens_estimate=100
        )
        assert prompt.content == "test prompt"
        assert prompt.hash == "abc123"
        assert prompt.hit_count == 0


class TestPromptCache:
    def test_cache_miss_on_empty(self):
        cache = PromptCache()
        result = cache.get("test prompt")
        assert result is None

    def test_cache_set_and_get(self):
        cache = PromptCache()
        cache.set("test prompt")
        result = cache.get("test prompt")
        assert result is not None
        assert result.content == "test prompt"

    def test_cache_hit_increments_counter(self):
        cache = PromptCache()
        cache.set("test prompt")
        cache.get("test prompt")
        cache.get("test prompt")
        stats = cache.get_stats()
        assert stats.cache_hits == 2

    def test_different_prompts_different_cache(self):
        cache = PromptCache()
        cache.set("prompt 1")
        cache.set("prompt 2")
        assert cache.get("prompt 1") is not None
        assert cache.get("prompt 2") is not None
        assert cache.get("prompt 1").content == "prompt 1"

    def test_cache_disabled(self):
        config = PromptCacheConfig(enabled=False)
        cache = PromptCache(config)
        cache.set("test prompt")
        result = cache.get("test prompt")
        assert result is None

    def test_max_size_eviction(self):
        config = PromptCacheConfig(max_size=2)
        cache = PromptCache(config)
        cache.set("prompt 1")
        cache.set("prompt 2")
        cache.set("prompt 3")
        assert cache.get("prompt 1") is None
        assert cache.get("prompt 2") is not None
        assert cache.get("prompt 3") is not None

    def test_invalidate_specific(self):
        cache = PromptCache()
        cache.set("prompt 1")
        cached = cache.get("prompt 1")
        cache.invalidate(cached.hash)
        assert cache.get("prompt 1") is None

    def test_invalidate_all(self):
        cache = PromptCache()
        cache.set("prompt 1")
        cache.set("prompt 2")
        cache.invalidate()
        assert cache.get("prompt 1") is None
        assert cache.get("prompt 2") is None

    def test_tokens_estimate(self):
        cache = PromptCache()
        cached = cache.set("test prompt")
        assert cached.tokens_estimate > 0

    def test_hit_count_tracking(self):
        cache = PromptCache()
        cache.set("test prompt")
        cache.get("test prompt")
        cached = cache.get("test prompt")
        assert cached.hit_count == 2

    def test_cleanup_expired(self):
        config = PromptCacheConfig(ttl_seconds=1)
        cache = PromptCache(config)
        cache.set("test prompt")
        import time
        time.sleep(1.1)
        removed = cache.cleanup_expired()
        assert removed >= 1
        assert cache.get("test prompt") is None

    def test_reset_stats(self):
        cache = PromptCache()
        cache.set("prompt 1")
        cache.get("prompt 1")
        cache.reset_stats()
        stats = cache.get_stats()
        assert stats.total_requests == 0
        assert stats.cache_hits == 0

    def test_global_instance(self):
        from src.infrastructure.services.prompt_cache import prompt_cache
        assert isinstance(prompt_cache, PromptCache)
