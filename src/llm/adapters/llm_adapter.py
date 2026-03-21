"""
Unified LLM Adapter

Single adapter that works with multiple providers using LLM_API_KEY.
Provider is determined by LLM_PROVIDER env var.
"""
import os
import time
import json
from typing import Optional

from src.llm.ports.llm_port import LLMPort, LLMResponse, LLMConfig
from src.infrastructure.services.db import db, calculate_cost


class LLMAdapter(LLMPort):
    """
    Unified adapter for Groq, Gemini, and other OpenAI-compatible APIs.
    
    Usage:
        adapter = LLMAdapter()  # Uses LLM_API_KEY, LLM_PROVIDER, LLM_MODEL from env
        adapter = LLMAdapter(provider="groq", api_key="...", model="llama-3.3-70b-versatile")
    """

    PROVIDERS = {
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "standard_model": "llama-3.3-70b-versatile",
            "premium_model": "llama-3.3-70b-versatile",
        },
        "gemini": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/models",
            "standard_model": "gemini-1.5-flash",
            "premium_model": "gemini-1.5-pro",
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "standard_model": "gpt-4o-mini",
            "premium_model": "gpt-4o",
        },
        "ollama": {
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            "standard_model": "llama3.2",
            "premium_model": "llama3.2",
        },
    }

    def __init__(
        self,
        provider: str = None,
        api_key: str = None,
        model: str = None,
        base_url: str = None,
    ):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")
        
        provider_config = self.PROVIDERS.get(self.provider, self.PROVIDERS["groq"])
        
        if model:
            self.model = model
        elif os.getenv("LLM_MODEL"):
            self.model = os.getenv("LLM_MODEL")
        else:
            self.model = provider_config.get("standard_model", "llama-3.3-70b-versatile")
        
        self.base_url = base_url or provider_config.get("base_url")
        
        if self.provider == "ollama":
            self.api_key = self.api_key or "ollama"

    def get_provider_name(self) -> str:
        return self.provider

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(self, prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError(f"{self.provider} API key not configured")

        cfg = config or LLMConfig(model=self.model)
        start_time = time.time()

        if self.provider == "gemini":
            return await self._gemini_complete(prompt, cfg, start_time)
        else:
            return await self._openai_compatible_complete(prompt, cfg, start_time)

    async def _openai_compatible_complete(
        self, prompt: str, config: LLMConfig, start_time: float
    ) -> LLMResponse:
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens
        }

        async with httpx.AsyncClient(timeout=config.timeout) as client:
            url = f"{self.base_url}/chat/completions"
            response = await client.post(url, headers=headers, json=payload)

        latency = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise RuntimeError(f"{self.provider} API error: {response.status_code} - {response.text}")

        data = response.json()
        tokens = data.get("usage", {}).get("total_tokens", 0)
        cost = calculate_cost(config.model, tokens)

        db.save_metric(
            provider=self.provider,
            model=config.model,
            tokens_used=tokens,
            cost_usd=cost,
            latency_ms=latency
        )

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", config.model),
            provider=self.provider,
            tokens_used=tokens,
            cost_usd=cost,
            latency_ms=latency
        )

    async def _gemini_complete(
        self, prompt: str, config: LLMConfig, start_time: float
    ) -> LLMResponse:
        import httpx

        url = f"{self.base_url}/{config.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": config.temperature,
                "maxOutputTokens": config.max_tokens
            }
        }

        async with httpx.AsyncClient(timeout=config.timeout) as client:
            response = await client.post(url, json=payload)

        latency = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise RuntimeError(f"Gemini API error: {response.status_code}")

        data = response.json()
        content = data["candidates"][0]["content"]["parts"][0]["text"]

        tokens = len(prompt.split()) + len(content.split())
        cost = calculate_cost(config.model, tokens)

        db.save_metric(
            provider=self.provider,
            model=config.model,
            tokens_used=tokens,
            cost_usd=cost,
            latency_ms=latency
        )

        return LLMResponse(
            content=content,
            model=config.model,
            provider=self.provider,
            tokens_used=tokens,
            cost_usd=cost,
            latency_ms=latency
        )

    async def complete_structured(
        self,
        prompt: str,
        schema: dict,
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError(f"{self.provider} API key not configured")

        cfg = config or LLMConfig(model=self.model)
        start_time = time.time()

        if self.provider == "gemini":
            return await self._gemini_structured(prompt, schema, cfg, start_time)
        else:
            return await self._openai_compatible_structured(prompt, schema, cfg, start_time)

    async def _openai_compatible_structured(
        self, prompt: str, schema: dict, config: LLMConfig, start_time: float
    ) -> LLMResponse:
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        structured_prompt = f"""{prompt}

Respond ONLY with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

JSON Response:"""

        payload = {
            "model": config.model,
            "messages": [{"role": "user", "content": structured_prompt}],
            "temperature": 0.1,
            "max_tokens": config.max_tokens,
        }

        if self.provider == "groq":
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=config.timeout) as client:
            url = f"{self.base_url}/chat/completions"
            response = await client.post(url, headers=headers, json=payload)

        latency = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise RuntimeError(f"{self.provider} API error: {response.status_code}")

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", 0)
        cost = calculate_cost(config.model, tokens)

        try:
            json.loads(content)
        except json.JSONDecodeError:
            raise RuntimeError(f"{self.provider} did not return valid JSON")

        db.save_metric(
            provider=self.provider,
            model=config.model,
            tokens_used=tokens,
            cost_usd=cost,
            latency_ms=latency
        )

        return LLMResponse(
            content=content,
            model=data.get("model", config.model),
            provider=self.provider,
            tokens_used=tokens,
            cost_usd=cost,
            latency_ms=latency
        )

    async def _gemini_structured(
        self, prompt: str, schema: dict, config: LLMConfig, start_time: float
    ) -> LLMResponse:
        import httpx

        url = f"{self.base_url}/{config.model}:generateContent?key={self.api_key}"

        structured_prompt = f"""{prompt}

Respond ONLY with valid JSON matching this schema:
{json.dumps(schema, indent=2)}"""

        payload = {
            "contents": [{"parts": [{"text": structured_prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": config.max_tokens,
                "responseMimeType": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=config.timeout) as client:
            response = await client.post(url, json=payload)

        latency = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise RuntimeError(f"Gemini API error: {response.status_code}")

        data = response.json()
        content = data["candidates"][0]["content"]["parts"][0]["text"]
        tokens = len(prompt.split()) + len(content.split())
        cost = calculate_cost(config.model, tokens)

        db.save_metric(
            provider=self.provider,
            model=config.model,
            tokens_used=tokens,
            cost_usd=cost,
            latency_ms=latency
        )

        return LLMResponse(
            content=content,
            model=config.model,
            provider=self.provider,
            tokens_used=tokens,
            cost_usd=cost,
            latency_ms=latency
        )
