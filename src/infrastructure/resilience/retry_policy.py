"""
Exponential Backoff Retry Pattern

¿Qué es?
--------
Imaginate que llamás por teléfono y está ocupado:

1. Esperás 1 segundo, llamás → OCUPADO
2. Esperás 2 segundos, llamás → OCUPADO  
3. Esperás 4 segundos, llamás → OCUPADO
4. Esperás 8 segundos, llamás → OCUPADO
5. Esperás 16 segundos, llamás → OK!

Espera se duplica cada vez: 1, 2, 4, 8, 16... segundos

Parámetros:
-----------
- base_delay: 1 segundo (empieza acá)
- max_delay: 60 segundos (máximo a esperar)
- max_retries: 5 (cantidad de intentos)
- exponential_base: 2 (por cuánto se multiplica)

Cálculo:
---------
delay = min(base_delay * (exponential_base ^ attempt), max_delay)

attempt=0: delay = 1 * (2^0) = 1s
attempt=1: delay = 1 * (2^1) = 2s
attempt=2: delay = 1 * (2^2) = 4s
attempt=3: delay = 1 * (2^3) = 8s
attempt=4: delay = 1 * (2^4) = 16s
attempt=5: delay = min(32s, 60s) = 32s
"""
import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Callable, Awaitable, TypeVar, Union
from functools import wraps


T = TypeVar('T')


class RetryStrategy(str, Enum):
    FIXED = "fixed"               # Siempre el mismo delay
    LINEAR = "linear"             # Incrementa linealmente
    EXPONENTIAL = "exponential"   # Duplica cada vez (recomendado)
    FIBONACCI = "fibonacci"      # Secuencia de Fibonacci


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True
    jitter_range: float = 0.3
    

@dataclass
class RetryStats:
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_delay_seconds: float = 0.0
    last_attempt_at: Optional[datetime] = None
    errors: list = field(default_factory=list)


@dataclass
class RetryContext:
    attempt: int
    max_attempts: int
    delay: float
    error: Optional[Exception] = None
    
    @property
    def will_retry(self) -> bool:
        return self.attempt < self.max_attempts - 1
    
    @property
    def is_last_attempt(self) -> bool:
        return self.attempt == self.max_attempts - 1


class RetryExhausted(Exception):
    """Excepción cuando se agotaron los retries"""
    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Retry exhausted after {attempts} attempts. Last error: {last_error}")


class RetryableError(Exception):
    """Error que puede ser reintentado (transitorio)"""
    pass


def calculate_delay(
    attempt: int, 
    config: RetryConfig
) -> float:
    """Calcula el delay para un intento específico"""
    
    if config.strategy == RetryStrategy.FIXED:
        delay = config.base_delay
    
    elif config.strategy == RetryStrategy.LINEAR:
        delay = config.base_delay * (attempt + 1)
    
    elif config.strategy == RetryStrategy.EXPONENTIAL:
        delay = config.base_delay * (config.exponential_base ** attempt)
    
    elif config.strategy == RetryStrategy.FIBONACCI:
        a, b = 1, 1
        for _ in range(attempt):
            a, b = b, a + b
        delay = config.base_delay * a
    
    else:
        delay = config.base_delay
    
    delay = min(delay, config.max_delay)
    
    if config.jitter:
        jitter_amount = delay * config.jitter_range
        delay = delay + random.uniform(-jitter_amount, jitter_amount)
        delay = max(0.1, delay)
    
    return delay


async def retry_with_backoff(
    func: Callable[..., Awaitable[T]],
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> T:
    """
    Ejecuta una función async con retry y exponential backoff.
    
    Uso:
    ----
    @retry_with_backoff(config=RetryConfig(max_retries=5, base_delay=1.0))
    async def mi_funcion():
        return await api.call()
    
    # O directo:
    result = await retry_with_backoff(
        mi_funcion,
        RetryConfig(max_retries=3)
    )
    """
    config = config or RetryConfig()
    last_error = None
    
    for attempt in range(config.max_retries):
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)
            return result
            
        except Exception as e:
            last_error = e
            
            if attempt == config.max_retries - 1:
                raise RetryExhausted(config.max_retries, last_error)
            
            delay = calculate_delay(attempt, config)
            await asyncio.sleep(delay)
    
    raise RetryExhausted(config.max_retries, last_error)


def retry_decorator(config: Optional[RetryConfig] = None):
    """
    Decorador para retry con backoff.
    
    Uso:
    ----
    @retry_decorator(RetryConfig(max_retries=5))
    async def mi_funcion():
        return await api.call()
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_with_backoff(func, config, *args, **kwargs)
        return wrapper
    return decorator


class RetryPolicy:
    """
    Política de retry configurable con callbacks.
    
    Uso:
    ----
    policy = RetryPolicy()
    policy.on_retry(lambda ctx: logger.warning(f"Retry {ctx.attempt}"))
    policy.on_success(lambda: metrics.increment("success"))
    policy.on_failure(lambda ctx: alerts.send(f"Failed after {ctx.max_attempts}"))
    
    result = await policy.execute(mi_funcion)
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._on_retry: list[Callable[[RetryContext], None]] = []
        self._on_success: list[Callable[[], None]] = []
        self._on_failure: list[Callable[[RetryContext], None]] = []
        self.stats = RetryStats()
    
    def on_retry(self, callback: Callable[[RetryContext], None]):
        """Callback cuando se hace retry"""
        self._on_retry.append(callback)
        return self
    
    def on_success(self, callback: Callable[[], None]):
        """Callback cuando succeede"""
        self._on_success.append(callback)
        return self
    
    def on_failure(self, callback: Callable[[RetryContext], None]):
        """Callback cuando falla después de todos los retries"""
        self._on_failure.append(callback)
        return self
    
    async def execute(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Ejecuta una función con la política de retry"""
        last_error = None
        
        for attempt in range(self.config.max_retries):
            self.stats.total_attempts += 1
            self.stats.last_attempt_at = datetime.now(timezone.utc)
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = await asyncio.to_thread(func, *args, **kwargs)
                
                self.stats.successful_attempts += 1
                for callback in self._on_success:
                    callback()
                
                return result
                
            except Exception as e:
                last_error = e
                self.stats.errors.append(str(e))
                
                if attempt == self.config.max_retries - 1:
                    self.stats.failed_attempts += 1
                    context = RetryContext(
                        attempt=attempt,
                        max_attempts=self.config.max_retries,
                        delay=0,
                        error=e
                    )
                    for callback in self._on_failure:
                        callback(context)
                    raise RetryExhausted(self.config.max_retries, last_error)
                
                delay = calculate_delay(attempt, self.config)
                self.stats.total_delay_seconds += delay
                
                context = RetryContext(
                    attempt=attempt,
                    max_attempts=self.config.max_retries,
                    delay=delay,
                    error=e
                )
                
                for callback in self._on_retry:
                    callback(context)
                
                await asyncio.sleep(delay)
        
        raise RetryExhausted(self.config.max_retries, last_error)
    
    def get_stats(self) -> dict:
        """Retorna estadísticas de retry"""
        return {
            "config": {
                "max_retries": self.config.max_retries,
                "base_delay": self.config.base_delay,
                "max_delay": self.config.max_delay,
                "strategy": self.config.strategy.value,
                "jitter": self.config.jitter
            },
            "stats": {
                "total_attempts": self.stats.total_attempts,
                "successful_attempts": self.stats.successful_attempts,
                "failed_attempts": self.stats.failed_attempts,
                "total_delay_seconds": self.stats.total_delay_seconds,
                "last_attempt_at": self.stats.last_attempt_at.isoformat() if self.stats.last_attempt_at else None,
                "error_count": len(self.stats.errors)
            }
        }


class AsyncRetryHelper:
    """
    Helper para hacer retry de múltiples operaciones en paralelo.
    
    Uso:
    ----
    helper = AsyncRetryHelper()
    
    results = await helper.execute_all([
        (api_call_1, {"arg": 1}),
        (api_call_2, {"arg": 2}),
        (api_call_3, {"arg": 3}),
    ])
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.policy = RetryPolicy(config=self.config)
    
    async def execute_all(
        self, 
        calls: list[tuple[Callable, dict]]
    ) -> list:
        """Ejecuta múltiples llamadas con retry individual"""
        tasks = []
        
        for func, kwargs in calls:
            task = self.policy.execute(func, **kwargs)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def execute_first_success(
        self,
        calls: list[tuple[Callable, dict]],
        timeout: float = 30.0
    ) -> T:
        """Ejecuta hasta que una succeede"""
        tasks = []
        
        for func, kwargs in calls:
            task = asyncio.create_task(self.policy.execute(func, **kwargs))
            tasks.append(task)
        
        done, pending = await asyncio.wait(
            tasks,
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED
        )
        
        for task in pending:
            task.cancel()
        
        for task in done:
            result = task.result()
            if not isinstance(result, Exception):
                return result
        
        if done:
            raise done[0].result()
        
        raise TimeoutError("All calls timed out")
