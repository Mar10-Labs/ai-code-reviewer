"""
Circuit Breaker Pattern

¿Qué es?
--------
Imaginate un automático de luz en tu casa:
- Normal: la luz prende y apaga (CLOSED)
- Si hay un cortocircuito: el automático "salta" y corta (OPEN)
- Después de un rato, probás de nuevo (HALF-OPEN)
- Si funciona, vuelve a lo normal (CLOSED)

Estados:
--------
CLOSED → Todo funciona, requests pasan normalmente
   ↓ (N fallos)
OPEN → Circuit cortado, requests rechazados inmediatamente
   ↓ (después de timeout)
HALF-OPEN → Se permite 1 request de prueba
   ↓ (éxito/error)
CLOSED / OPEN
"""
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import asyncio
import time


class CircuitState(Enum):
    CLOSED = "closed"    # Normal - acepta requests
    OPEN = "open"        # Cortado - rechaza requests
    HALF_OPEN = "half_open"  # Probando - 1 request de prueba


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Cuántos fallos abren el circuit
    success_threshold: int = 2       # Cuántos éxitos lo cierran (half-open → closed)
    timeout: float = 60.0           # Segundos antes de probar de nuevo
    half_open_max_calls: int = 1     # Requests permitidos en half-open


@dataclass
class CircuitBreakerStats:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_state_change: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CircuitBreakerOpen(Exception):
    """Excepción cuando el circuit está abierto"""
    pass


class CircuitBreaker:
    """
    Circuit Breaker - Previene cascade failures
    
    Ejemplo de uso:
    -----------
    cb = CircuitBreaker(failure_threshold=5, timeout=60)
    
    try:
        resultado = cb.call(lambda: mi_funcion_que_puede_fallar())
    except CircuitBreakerOpen:
        print("Circuit abierto! No se puede llamar ahora")
    
    También puedes usarlo como decorador:
    -----------
    @CircuitBreaker.decorator(failure_threshold=3)
    async def mi_llamada():
        return await api.externa()
    """
    
    def __init__(self, name: str = "default", config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float = 0
        self.half_open_calls = 0
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
    
    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN
    
    def _should_allow_request(self) -> bool:
        """Decide si se permite el request según el estado"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check si pasó el timeout
            time_since_failure = time.time() - self.last_failure_time
            if time_since_failure >= self.config.timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
        
        # HALF_OPEN: solo 1 request a la vez
        if self.half_open_calls < self.config.half_open_max_calls:
            self.half_open_calls += 1
            return True
        return False
    
    def _transition_to(self, new_state: CircuitState):
        """Transiciona a un nuevo estado"""
        if self.state != new_state:
            self.state = new_state
            self.stats.state_changes += 1
            self.stats.last_state_change = datetime.now(timezone.utc)
            
            # Reset counters según el estado
            if new_state == CircuitState.CLOSED:
                self.failure_count = 0
                self.success_count = 0
            elif new_state == CircuitState.HALF_OPEN:
                self.half_open_calls = 0
                self.success_count = 0
    
    def _on_success(self):
        """Maneja un éxito"""
        self.stats.successful_calls += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            # En closed, reseteamos failure count con cada éxito
            self.failure_count = 0
    
    def _on_failure(self):
        """Maneja un fallo"""
        self.stats.failed_calls += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # En half-open, cualquier fallo vuelve a abrir
            self._transition_to(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
    
    async def call(self, func, *args, **kwargs):
        """
        Ejecuta una función con Circuit Breaker
        
        Args:
            func: Función async a ejecutar
            *args, **kwargs: Argumentos para la función
        
        Returns:
            El resultado de la función
        
        Raises:
            CircuitBreakerOpen: Si el circuit está abierto
        """
        async with self._lock:
            self.stats.total_calls += 1
            
            if not self._should_allow_request():
                self.stats.rejected_calls += 1
                raise CircuitBreakerOpen(
                    f"Circuit '{self.name}' is OPEN. "
                    f"Wait {self.config.timeout}s before retry."
                )
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            async with self._lock:
                self._on_success()
            
            return result
            
        except Exception as e:
            async with self._lock:
                self._on_failure()
            raise
    
    def call_sync(self, func, *args, **kwargs):
        """Versión síncrona para funciones que no son async"""
        self.stats.total_calls += 1
        
        if not self._should_allow_request():
            self.stats.rejected_calls += 1
            raise CircuitBreakerOpen(
                f"Circuit '{self.name}' is OPEN"
            )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    @staticmethod
    def decorator(failure_threshold: int = 5, timeout: float = 60.0, name: str = None):
        """Decorador para envolver funciones con Circuit Breaker"""
        def decorator_func(func):
            cb_name = name or func.__name__
            cb = CircuitBreaker(name=cb_name, config=CircuitBreakerConfig(
                failure_threshold=failure_threshold,
                timeout=timeout
            ))
            
            async def wrapper(*args, **kwargs):
                return await cb.call(func, *args, **kwargs)
            
            wrapper.circuit_breaker = cb
            wrapper.__name__ = func.__name__
            return wrapper
        return decorator_func
    
    def get_status(self) -> dict:
        """Retorna el estado actual del circuit breaker"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "rejected_calls": self.stats.rejected_calls,
                "state_changes": self.stats.state_changes,
                "last_state_change": self.stats.last_state_change.isoformat()
            }
        }
    
    def reset(self):
        """Resetea el circuit breaker a estado inicial"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.stats = CircuitBreakerStats()
