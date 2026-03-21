"""
Rate Limiter Pattern

¿Qué es?
--------
Imaginate un surtidor de nafta:
- Tiene una válvula que limita a 50L/min
- Si ponés 100L/min, la válvula reduce el flujo
- Evita que el tanque explote por sobrecarga

GitHub API tiene límites:
- 5000 requests/hora (autenticado)
- 100 comments/hora por PR
- 30 reviews/hora

Token Bucket Algorithm:
--------------------
┌─────────────────────────────────────────┐
│                  Bucket                    │
│  ┌─────────────────────────────────┐    │
│  │  tokens: 50                      │    │
│  │  refill_rate: 1 por segundo      │    │
│  │  max_tokens: 50                  │    │
│  └─────────────────────────────────┘    │
│                                          │
│  acquire() → tokens-- → proceed          │
│  acquire() → tokens-- → proceed          │
│  acquire() → tokens-- → proceed          │
│  ...                                     │
│  acquire() → tokens=0 → WAIT            │
└─────────────────────────────────────────┘
"""
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Callable, Awaitable
from collections import defaultdict


class RateLimitStrategy(str, Enum):
    TOKEN_BUCKET = "token_bucket"     # Token bucket clásico
    SLIDING_WINDOW = "sliding_window"   # Ventana deslizante
    FIXED_WINDOW = "fixed_window"       # Ventana fija


@dataclass
class RateLimitConfig:
    requests_per_second: float = 10.0
    requests_per_minute: float = 500.0
    requests_per_hour: float = 5000.0
    burst_size: int = 20
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET


@dataclass
class RateLimitStats:
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0
    wait_time_seconds: float = 0.0
    last_request_time: Optional[float] = None
    tokens_available: float = 0.0


class RateLimitExceeded(Exception):
    """Excepción cuando se excede el rate limit"""
    def __init__(self, retry_after: float = 1.0):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after:.2f}s")


class RateLimiter:
    """
    Rate Limiter con Token Bucket Algorithm.
    
    Uso:
    ----
    # Límite de 10 requests/segundo con burst de 20
    limiter = RateLimiter(
        requests_per_second=10.0,
        burst_size=20
    )
    
    # Adquirir permiso
    await limiter.acquire()
    # ... hacer request ...
    
    # Con función callback
    await limiter.acquire_with_callback(
        lambda: github_api.call()
    )
    """
    
    def __init__(
        self, 
        config: Optional[RateLimitConfig] = None,
        name: str = "default"
    ):
        self.config = config or RateLimitConfig()
        self.name = name
        
        self._tokens: float = self.config.burst_size
        self._last_refill: float = time.time()
        self._lock = asyncio.Lock()
        self._stats = RateLimitStats(tokens_available=self._tokens)
        
        self._requests_this_second = 0
        self._requests_this_minute = 0
        self._requests_this_hour = 0
        self._second_reset_at = time.time()
        self._minute_reset_at = time.time()
        self._hour_reset_at = time.time()
    
    def _refill_tokens(self):
        """Refill tokens basándose en el tiempo transcurrido"""
        now = time.time()
        elapsed = now - self._last_refill
        
        tokens_to_add = elapsed * self.config.requests_per_second
        self._tokens = min(
            self._tokens + tokens_to_add,
            self.config.burst_size
        )
        self._last_refill = now
    
    def _refill_counters(self):
        """Reset counters basándose en ventanas de tiempo"""
        now = time.time()
        
        if now - self._second_reset_at >= 1.0:
            self._requests_this_second = 0
            self._second_reset_at = now
        
        if now - self._minute_reset_at >= 60.0:
            self._requests_this_minute = 0
            self._minute_reset_at = now
        
        if now - self._hour_reset_at >= 3600.0:
            self._requests_this_hour = 0
            self._hour_reset_at = now
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Adquiere permiso para hacer N requests.
        Si no hay tokens disponibles, espera hasta que haya.
        
        Returns:
            True si se adquirió permiso
        
        Raises:
            RateLimitExceeded si se excede el límite por hora
        """
        async with self._lock:
            self._refill_tokens()
            self._refill_counters()
            
            self._stats.total_requests += 1
            
            if self._requests_this_hour >= self.config.requests_per_hour:
                raise RateLimitExceeded(retry_after=3600.0)
            
            if self._requests_this_minute >= self.config.requests_per_minute:
                wait_time = 60.0 - (time.time() - self._minute_reset_at)
                raise RateLimitExceeded(retry_after=wait_time)
            
            while self._tokens < tokens:
                await asyncio.sleep(0.1)
                self._refill_tokens()
            
            self._tokens -= tokens
            self._requests_this_second += 1
            self._requests_this_minute += 1
            self._requests_this_hour += 1
            
            self._stats.allowed_requests += 1
            self._stats.tokens_available = self._tokens
            self._stats.last_request_time = time.time()
            
            return True
    
    async def acquire_or_raise(self, tokens: int = 1):
        """Versión que levanta excepción si no puede adquirir"""
        await self.acquire(tokens)
    
    async def try_acquire(self, tokens: int = 1) -> bool:
        """
        Intenta adquirir permiso sin esperar.
        
        Returns:
            True si se adquirió, False si no hay tokens
        """
        async with self._lock:
            self._refill_tokens()
            self._refill_counters()
            
            if self._requests_this_hour >= self.config.requests_per_hour:
                return False
            
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._requests_this_second += 1
                self._requests_this_minute += 1
                self._requests_this_hour += 1
                self._stats.total_requests += 1
                self._stats.allowed_requests += 1
                return True
            
            return False
    
    async def wait_if_needed(self, tokens: int = 1):
        """Espera hasta que haya tokens disponibles (sin excepción)"""
        while True:
            if await self.try_acquire(tokens):
                return
            await asyncio.sleep(0.5)
    
    async def execute(self, func: Callable[..., Awaitable], *args, **kwargs):
        """
        Ejecuta una función async con rate limiting.
        
        Usage:
            result = await limiter.execute(github_api.call, arg1, arg2)
        """
        await self.acquire()
        return await func(*args, **kwargs)
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """Retorna el tiempo estimado de espera en segundos"""
        self._refill_tokens()
        
        if self._requests_this_hour >= self.config.requests_per_hour:
            return 3600.0 - (time.time() - self._hour_reset_at)
        
        if self._tokens < tokens:
            tokens_needed = tokens - self._tokens
            return tokens_needed / self.config.requests_per_second
        
        return 0.0
    
    def get_stats(self) -> dict:
        """Retorna estadísticas del rate limiter"""
        return {
            "name": self.name,
            "tokens_available": self._tokens,
            "max_tokens": self.config.burst_size,
            "requests_per_second": self.config.requests_per_second,
            "requests_this_second": self._requests_this_second,
            "requests_this_minute": self._requests_this_minute,
            "requests_this_hour": self._requests_this_hour,
            "limits": {
                "per_hour": self.config.requests_per_hour,
                "per_minute": self.config.requests_per_minute,
                "per_second": self.config.requests_per_second
            },
            "stats": {
                "total_requests": self._stats.total_requests,
                "allowed_requests": self._stats.allowed_requests,
                "rejected_requests": self._stats.rejected_requests,
                "wait_time_seconds": self._stats.wait_time_seconds,
                "last_request_time": self._stats.last_request_time
            }
        }
    
    def reset(self):
        """Resetea el rate limiter"""
        self._tokens = self.config.burst_size
        self._requests_this_second = 0
        self._requests_this_minute = 0
        self._requests_this_hour = 0
        self._stats = RateLimitStats(tokens_available=self._tokens)


class MultiRateLimiter:
    """
    Rate limiter para múltiples endpoints con límites diferentes.
    
    Uso:
    ----
    limiter = MultiRateLimiter()
    
    limiter.add_limit("github_api", requests_per_hour=5000)
    limiter.add_limit("github_comments", requests_per_hour=100)
    limiter.add_limit("github_reviews", requests_per_hour=30)
    
    await limiter.acquire("github_api")
    await limiter.acquire("github_comments")
    """
    
    def __init__(self):
        self._limiters: dict[str, RateLimiter] = {}
        self._configs: dict[str, RateLimitConfig] = {}
    
    def add_limit(
        self, 
        name: str, 
        requests_per_second: float = 10,
        requests_per_hour: float = 5000,
        burst_size: int = 20
    ):
        """Agrega un nuevo límite"""
        config = RateLimitConfig(
            requests_per_second=requests_per_second,
            requests_per_hour=requests_per_hour,
            burst_size=burst_size
        )
        self._configs[name] = config
        self._limiters[name] = RateLimiter(config=config, name=name)
    
    async def acquire(self, name: str, tokens: int = 1):
        """Adquiere permiso para un endpoint específico"""
        if name not in self._limiters:
            raise ValueError(f"Unknown limit: {name}. Add it first with add_limit()")
        await self._limiters[name].acquire(tokens)
    
    async def try_acquire(self, name: str, tokens: int = 1) -> bool:
        """Intenta adquirir sin esperar"""
        if name not in self._limiters:
            return False
        return await self._limiters[name].try_acquire(tokens)
    
    def get_stats(self, name: str = None) -> dict:
        """Retorna estadísticas de un endpoint o todos"""
        if name:
            return self._limiters[name].get_stats()
        return {name: limiter.get_stats() for name, limiter in self._limiters.items()}


# Instancia global para GitHub API
_github_limiter: Optional[MultiRateLimiter] = None


def get_github_limiter() -> MultiRateLimiter:
    """Retorna la instancia global del rate limiter de GitHub"""
    global _github_limiter
    if _github_limiter is None:
        _github_limiter = MultiRateLimiter()
        _github_limiter.add_limit("github_api", requests_per_hour=5000)
        _github_limiter.add_limit("github_comments", requests_per_hour=100)
        _github_limiter.add_limit("github_reviews", requests_per_hour=30)
    return _github_limiter
