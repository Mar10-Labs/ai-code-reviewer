"""
LLM Fallback Chain

¿Qué es?
--------
Imaginate que tu celular tiene 3 compañías:
- Tenés signal (Groq)
- Si no hay signal, usás Movicom (Gemini)
- Si tampoco hay, usás Personal (Ollama)
- Si ninguno funciona, dejás un mensaje de voicemail (Fallback)

Patrón Chain of Responsibility con Fallback:
------------------------------------------
Request
   ↓
Groq → [OK] → Response
   ↓ [FAIL/OPEN]
Gemini → [OK] → Response
   ↓ [FAIL/OPEN]
Ollama → [OK] → Response
   ↓ [FAIL]
Fallback → "Service temporarily unavailable, we noticed the issue"
"""
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from src.llm.ports.llm_port import LLMPort, LLMResponse, LLMConfig
from src.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen
)


class FallbackReason(str, Enum):
    CIRCUIT_OPEN = "circuit_open"
    TIMEOUT = "timeout"
    ERROR = "error"
    NOT_AVAILABLE = "not_available"


@dataclass
class FallbackResponse(LLMResponse):
    """Respuesta cuando todos los LLMs fallan"""
    is_fallback: bool = True
    fallback_reason: Optional[str] = None
    providers_tried: list[str] = field(default_factory=list)


@dataclass
class FallbackConfig:
    timeout_per_provider: float = 60.0
    max_retries_per_provider: int = 1
    enable_circuit_breaker: bool = True
    fallback_message: str = "Service temporarily unavailable. Please try again later."


class LLMFallbackChain:
    """
    Chain of Responsibility con Fallback para LLMs.
    
    Uso:
    ----
    chain = LLMFallbackChain()
    chain.add_provider(groq_adapter, name="groq")
    chain.add_provider(gemini_adapter, name="gemini")
    chain.add_provider(ollama_adapter, name="ollama")
    
    # Si todos fallan, usa esta función
    chain.set_fallback(lambda: FallbackResponse(...))
    
    # Ejecutar
    response = await chain.complete(prompt)
    """
    
    def __init__(self, config: FallbackConfig = None):
        self._providers: list[tuple[LLMPort, str, CircuitBreaker]] = []
        self._fallback: Optional[Callable] = None
        self._config = config or FallbackConfig()
    
    def add_provider(self, adapter: LLMPort, name: str = None, circuit_breaker: CircuitBreaker = None):
        """Agrega un provider a la chain"""
        cb = circuit_breaker or CircuitBreaker(
            name=name or adapter.get_provider_name(),
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout=60.0
            )
        )
        self._providers.append((adapter, name or adapter.get_provider_name(), cb))
    
    def set_fallback(self, fallback_fn: Callable[[], LLMResponse]):
        """Define el fallback cuando todos fallan"""
        self._fallback = fallback_fn
    
    async def complete(self, prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
        """
        Ejecuta la chain: intenta cada provider en orden hasta que uno funcione.
        """
        providers_tried = []
        last_error = None
        
        for adapter, name, cb in self._providers:
            providers_tried.append(name)
            
            if not adapter.is_available():
                continue
            
            if self._config.enable_circuit_breaker and cb.is_open:
                continue
            
            try:
                if asyncio.iscoroutinefunction(adapter.complete):
                    response = await asyncio.wait_for(
                        adapter.complete(prompt, config),
                        timeout=self._config.timeout_per_provider
                    )
                else:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(adapter.complete, prompt, config),
                        timeout=self._config.timeout_per_provider
                    )
                
                response.providers_tried = providers_tried.copy()
                return response
                
            except asyncio.TimeoutError:
                last_error = FallbackReason.TIMEOUT
                continue
                
            except CircuitBreakerOpen:
                last_error = FallbackReason.CIRCUIT_OPEN
                continue
                
            except Exception as e:
                last_error = FallbackReason.ERROR
                continue
        
        if self._fallback:
            response = self._fallback()
            if hasattr(response, 'providers_tried'):
                response.providers_tried = providers_tried
            if hasattr(response, 'fallback_reason'):
                response.fallback_reason = last_error.value if last_error else "all_failed"
            return response
        
        return FallbackResponse(
            content=self._config.fallback_message,
            model="fallback",
            provider="none",
            tokens_used=0,
            cost_usd=0,
            latency_ms=0,
            is_fallback=True,
            fallback_reason=last_error.value if last_error else "all_failed",
            providers_tried=providers_tried
        )
    
    async def complete_structured(
        self, 
        prompt: str, 
        schema: dict,
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """Versión estructurada (JSON) de complete"""
        providers_tried = []
        last_error = None
        
        for adapter, name, cb in self._providers:
            providers_tried.append(name)
            
            if not adapter.is_available():
                continue
            
            if self._config.enable_circuit_breaker and cb.is_open:
                continue
            
            try:
                if asyncio.iscoroutinefunction(adapter.complete_structured):
                    response = await asyncio.wait_for(
                        adapter.complete_structured(prompt, schema, config),
                        timeout=self._config.timeout_per_provider
                    )
                else:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(adapter.complete_structured, prompt, schema, config),
                        timeout=self._config.timeout_per_provider
                    )
                
                return response
                
            except asyncio.TimeoutError:
                last_error = FallbackReason.TIMEOUT
                continue
            except CircuitBreakerOpen:
                last_error = FallbackReason.CIRCUIT_OPEN
                continue
            except Exception as e:
                last_error = FallbackReason.ERROR
                continue
        
        return FallbackResponse(
            content=self._config.fallback_message,
            model="fallback",
            provider="none",
            is_fallback=True,
            fallback_reason=last_error.value if last_error else "all_failed",
            providers_tried=providers_tried
        )
    
    def get_provider_status(self) -> list[dict]:
        """Retorna el estado de cada provider"""
        status = []
        for adapter, name, cb in self._providers:
            status.append({
                "name": name,
                "available": adapter.is_available(),
                "circuit_state": cb.state.value,
                "circuit_stats": cb.stats.__dict__
            })
        return status


class DefaultLLMChain:
    """
    Chain por defecto que intenta Groq → Gemini → Ollama → Fallback.
    
    Uso simple:
    -----------
    chain = DefaultLLMChain()
    response = await chain.complete(prompt)
    """
    
    def __init__(self):
        self._chain: Optional[LLMFallbackChain] = None
        self._initialize_chain()
    
    def _initialize_chain(self):
        from src.llm.adapters.groq_adapter import GroqAdapter
        from src.llm.adapters.gemini_adapter import GeminiAdapter
        from src.llm.adapters.ollama_adapter import OllamaAdapter
        
        self._chain = LLMFallbackChain()
        
        groq = GroqAdapter()
        if groq.is_available():
            self._chain.add_provider(groq, name="groq")
        
        gemini = GeminiAdapter()
        if gemini.is_available():
            self._chain.add_provider(gemini, name="gemini")
        
        ollama = OllamaAdapter()
        self._chain.add_provider(ollama, name="ollama")
        
        self._chain.set_fallback(lambda: FallbackResponse(
            content="AI Code Reviewer temporarily unavailable. Please try again in a few minutes.",
            model="fallback",
            provider="none",
            tokens_used=0,
            cost_usd=0,
            latency_ms=0,
            is_fallback=True,
            fallback_reason="all_providers_failed"
        ))
    
    async def complete(self, prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
        return await self._chain.complete(prompt, config)
    
    async def complete_structured(
        self, 
        prompt: str, 
        schema: dict,
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        return await self._chain.complete_structured(prompt, schema, config)
    
    def get_provider_status(self) -> list[dict]:
        return self._chain.get_provider_status()
