import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone


@dataclass
class CachedPrompt:
    content: str
    hash: str
    created_at: datetime
    last_used: datetime
    tokens_estimate: int
    hit_count: int = 0


@dataclass
class CacheStats:
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    tokens_saved: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    @property
    def savings_percent(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100


class PromptCacheConfig:
    DEFAULT_TTL_SECONDS = 3600
    DEFAULT_MAX_SIZE = 100

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_size: int = DEFAULT_MAX_SIZE,
        enabled: bool = True
    ):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self.enabled = enabled


class PromptCache:
    def __init__(self, config: Optional[PromptCacheConfig] = None):
        self.config = config or PromptCacheConfig()
        self._cache: dict[str, CachedPrompt] = {}
        self._stats = CacheStats()
        self._lock = None

    def _get_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _estimate_tokens(self, content: str) -> int:
        return len(content) // 4

    def get(self, prompt: str) -> Optional[CachedPrompt]:
        if not self.config.enabled:
            return None

        self._stats.total_requests += 1
        prompt_hash = self._get_hash(prompt)

        cached = self._cache.get(prompt_hash)
        if cached is None:
            self._stats.cache_misses += 1
            return None

        age = (datetime.now(timezone.utc) - cached.created_at).total_seconds()
        if age > self.config.ttl_seconds:
            del self._cache[prompt_hash]
            self._stats.cache_misses += 1
            return None

        cached.last_used = datetime.now(timezone.utc)
        cached.hit_count += 1
        self._stats.cache_hits += 1
        self._stats.tokens_saved += cached.tokens_estimate

        return cached

    def set(self, prompt: str) -> CachedPrompt:
        if not self.config.enabled:
            return CachedPrompt(
                content=prompt,
                hash=self._get_hash(prompt),
                created_at=datetime.now(timezone.utc),
                last_used=datetime.now(timezone.utc),
                tokens_estimate=self._estimate_tokens(prompt)
            )

        prompt_hash = self._get_hash(prompt)

        if prompt_hash in self._cache:
            cached = self._cache[prompt_hash]
            cached.last_used = datetime.now(timezone.utc)
            return cached

        if len(self._cache) >= self.config.max_size:
            self._evict_oldest()

        cached = CachedPrompt(
            content=prompt,
            hash=prompt_hash,
            created_at=datetime.now(timezone.utc),
            last_used=datetime.now(timezone.utc),
            tokens_estimate=self._estimate_tokens(prompt)
        )

        self._cache[prompt_hash] = cached
        return cached

    def _evict_oldest(self):
        if not self._cache:
            return

        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_used
        )
        del self._cache[oldest_key]

    def invalidate(self, prompt_hash: str = None):
        if prompt_hash:
            self._cache.pop(prompt_hash, None)
        else:
            self._cache.clear()

    def get_stats(self) -> CacheStats:
        return self._stats

    def reset_stats(self):
        self._stats = CacheStats()

    def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        expired_keys = [
            k for k, v in self._cache.items()
            if (now - v.created_at).total_seconds() > self.config.ttl_seconds
        ]

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)


prompt_cache = PromptCache()
