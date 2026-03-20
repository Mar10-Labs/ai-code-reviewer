import os
import time
import json
from typing import Optional

from src.llm.ports.llm_port import LLMPort, LLMResponse, LLMConfig


class GeminiAdapter(LLMPort):
    """Google Gemini Adapter"""

    def __init__(self, api_key: str = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def get_provider_name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(self, prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("Gemini API key not configured")

        import httpx

        cfg = config or LLMConfig(model=self.model)

        url = f"{self.base_url}/{cfg.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens
            }
        }

        start_time = time.time()

        async with httpx.AsyncClient(timeout=cfg.timeout) as client:
            response = await client.post(url, json=payload)

        latency = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise RuntimeError(f"Gemini API error: {response.status_code}")

        data = response.json()

        content = data["candidates"][0]["content"]["parts"][0]["text"]

        # Estimate tokens (rough)
        tokens = len(prompt.split()) + len(content.split())

        return LLMResponse(
            content=content,
            model=cfg.model,
            provider="gemini",
            tokens_used=tokens,
            cost_usd=0.001,  # Rough estimate
            latency_ms=latency
        )

    async def complete_structured(
        self,
        prompt: str,
        schema: dict,
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("Gemini API key not configured")

        import httpx

        cfg = config or LLMConfig(model=self.model)

        url = f"{self.base_url}/{cfg.model}:generateContent?key={self.api_key}"

        structured_prompt = f"""{prompt}

Respond ONLY with valid JSON matching this schema:
{json.dumps(schema, indent=2)}"""

        payload = {
            "contents": [{"parts": [{"text": structured_prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": cfg.max_tokens,
                "responseMimeType": "application/json"
            }
        }

        start_time = time.time()

        async with httpx.AsyncClient(timeout=cfg.timeout) as client:
            response = await client.post(url, json=payload)

        latency = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise RuntimeError(f"Gemini API error: {response.status_code}")

        data = response.json()
        content = data["candidates"][0]["content"]["parts"][0]["text"]

        return LLMResponse(
            content=content,
            model=cfg.model,
            provider="gemini",
            latency_ms=latency
        )
