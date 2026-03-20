import os
import time
import json
from typing import Optional

from src.llm.ports.llm_port import LLMPort, LLMResponse, LLMConfig


class GroqAdapter(LLMPort):
    """Groq API Adapter - Fast, free tier available"""

    def __init__(self, api_key: str = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"

    def get_provider_name(self) -> str:
        return "groq"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(self, prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("Groq API key not configured")

        import httpx

        cfg = config or LLMConfig(model=self.model)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": cfg.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens
        }

        start_time = time.time()

        async with httpx.AsyncClient(timeout=cfg.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )

        latency = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise RuntimeError(f"Groq API error: {response.status_code} - {response.text}")

        data = response.json()

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data["model"],
            provider="groq",
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            cost_usd=0,  # Free tier
            latency_ms=latency
        )

    async def complete_structured(
        self,
        prompt: str,
        schema: dict,
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("Groq API key not configured")

        import httpx

        cfg = config or LLMConfig(model=self.model)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        structured_prompt = f"""{prompt}

Respond ONLY with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

JSON Response:"""

        payload = {
            "model": cfg.model,
            "messages": [{"role": "user", "content": structured_prompt}],
            "temperature": 0.1,  # Low temperature for structured output
            "max_tokens": cfg.max_tokens,
            "response_format": {"type": "json_object"}
        }

        start_time = time.time()

        async with httpx.AsyncClient(timeout=cfg.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )

        latency = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise RuntimeError(f"Groq API error: {response.status_code}")

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        try:
            json.loads(content)
        except json.JSONDecodeError:
            raise RuntimeError("Groq did not return valid JSON")

        return LLMResponse(
            content=content,
            model=data["model"],
            provider="groq",
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            cost_usd=0,
            latency_ms=latency
        )
