import os
import time
import json
from typing import Optional

from src.llm.ports.llm_port import LLMPort, LLMResponse, LLMConfig


class OllamaAdapter(LLMPort):
    """Ollama Adapter - Local LLM (free, private)"""

    def __init__(self, base_url: str = None, model: str = "llama3.2"):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model

    def get_provider_name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        import httpx
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    async def complete(self, prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
        import httpx

        cfg = config or LLMConfig(model=self.model)

        payload = {
            "model": cfg.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": cfg.temperature,
                "num_predict": cfg.max_tokens
            }
        }

        start_time = time.time()

        async with httpx.AsyncClient(timeout=cfg.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )

        latency = (time.time() - start_time) * 1000

        if response.status_code != 200:
            raise RuntimeError(f"Ollama API error: {response.status_code}")

        data = response.json()

        return LLMResponse(
            content=data.get("response", ""),
            model=cfg.model,
            provider="ollama",
            tokens_used=data.get("eval_count", 0),
            cost_usd=0,  # Free (local)
            latency_ms=latency
        )

    async def complete_structured(
        self,
        prompt: str,
        schema: dict,
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        structured_prompt = f"""{prompt}

Respond ONLY with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

JSON Response:"""

        return await self.complete(structured_prompt, config)
