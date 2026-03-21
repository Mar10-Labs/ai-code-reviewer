"""
Resilience Patterns Module

Contiene patrones de resilience para sistemas distribuidos:
- Circuit Breaker: Previene cascade failures
"""
from src.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerStats,
    CircuitBreakerOpen,
    CircuitState
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerStats",
    "CircuitBreakerOpen",
    "CircuitState"
]
