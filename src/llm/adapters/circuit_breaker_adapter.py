"""
Circuit Breaker Wrapper para LLM Adapters

Envuelve un LLMPort con Circuit Breaker para prevenir cascade failures.
"""
from typing import Optional
from src.llm.ports.llm_port import LLMPort, LLMResponse, LLMConfig
from src.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitState
)


class LLMCircuitBreakerAdapter(LLMPort):
    """
    Adapter que envuelve otro LLMPort con Circuit Breaker.
    
    Uso:
    ----
    groq = GroqAdapter()
    cb_groq = LLMCircuitBreakerAdapter(groq, name="groq")
    
    # Ahora groq tiene protección de circuit breaker
    response = await cb_groq.complete(prompt)
    """
    
    def __init__(
        self, 
        adapter: LLMPort,
        name: str = None,
        config: CircuitBreakerConfig = None
    ):
        self._adapter = adapter
        self._name = name or adapter.get_provider_name()
        self._circuit_breaker = CircuitBreaker(
            name=self._name,
            config=config or CircuitBreakerConfig(
                failure_threshold=5,      # 5 fallos = abre
                success_threshold=2,      # 2 éxitos en half-open = cierra
                timeout=60.0             # 60s antes de probar
            )
        )
    
    def get_provider_name(self) -> str:
        return f"{self._adapter.get_provider_name()}_protected"
    
    def is_available(self) -> bool:
        return self._adapter.is_available() and not self._circuit_breaker.is_open
    
    async def complete(self, prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
        async def _call():
            return await self._adapter.complete(prompt, config)
        
        return await self._circuit_breaker.call(_call)
    
    async def complete_structured(
        self, 
        prompt: str, 
        schema: dict,
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        async def _call():
            return await self._adapter.complete_structured(prompt, schema, config)
        
        return await self._circuit_breaker.call(_call)
    
    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker
    
    def get_status(self) -> dict:
        return self._circuit_breaker.get_status()
    
    def reset(self):
        self._circuit_breaker.reset()
