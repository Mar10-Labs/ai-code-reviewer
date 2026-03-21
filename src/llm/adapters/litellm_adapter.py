import os
import time
import json
from typing import Optional

from src.llm.ports.llm_port import LLMPort, LLMResponse, LLMConfig


class LiteLLMAdapter(LLMPort):
    """Unified LLM Adapter using LiteLLM - supports 100+ providers"""

    PROVIDER_MODEL_MAP = {
        "groq": "groq/llama-3.3-70b-versatile",
        "gemini": "gemini/gemini-1.5-flash",
        "openai": "gpt-4o-mini",
        "anthropic": "anthropic/claude-3-haiku-20240307",
        "ollama": "ollama/llama3.2",
        "huggingface": "huggingface/mistralai/Mistral-7B-Instruct-v0.2",
        "ai_studio": "ai_studio/gemini-1.5-flash",
    }

    def __init__(
        self,
        provider: str = None,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        api_base: str = None,
        timeout: int = 60,
    ):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        self.api_key = api_key or os.getenv(f"{self.provider.upper()}_API_KEY")
        self.base_url = base_url or api_base or os.getenv("LITELLM_BASE_URL")

        if model:
            self.model = model if "/" in model else f"{self.provider}/{model}"
        else:
            mapped = self.PROVIDER_MODEL_MAP.get(self.provider, "")
            if mapped:
                self.model = mapped
            else:
                self.model = f"{self.provider}/default"

        self.timeout = timeout
        self._client = None

    def get_provider_name(self) -> str:
        return f"litellm-{self.provider}"

    def _get_litellm_params(self, config: Optional[LLMConfig] = None) -> dict:
        cfg = config or LLMConfig(model=self.model)

        params = {
            "model": self.model,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }

        if self.api_key:
            params["api_key"] = self.api_key

        if self.base_url:
            params["api_base"] = self.base_url

        return params

    def _get_env_for_provider(self) -> dict:
        env_config = {}
        provider_upper = self.provider.upper()

        if self.provider == "groq":
            env_config["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
        elif self.provider == "gemini":
            env_config["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")
        elif self.provider == "openai":
            env_config["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
        elif self.provider == "anthropic":
            env_config["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
        elif self.provider == "ollama":
            env_config["OLLAMA_BASE_URL"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        return {k: v for k, v in env_config.items() if v}

    def is_available(self) -> bool:
        if self.api_key:
            return True
        if self.provider == "ollama":
            return self._check_ollama()
        return True

    def _check_ollama(self) -> bool:
        if self.base_url:
            try:
                import httpx
                with httpx.Client(timeout=5) as client:
                    response = client.get(f"{self.base_url}/api/tags")
                    return response.status_code == 200
            except Exception:
                return False
        return True

    async def complete(self, prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
        import httpx

        params = self._get_litellm_params(config)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": params["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": params["temperature"],
            "max_tokens": params["max_tokens"],
        }

        base_url = params.get("api_base", "https://llm.api.ai-code-reviewer.dev/v1")
        if not base_url.startswith("http"):
            base_url = f"https://llm.api.ai-code-reviewer.dev/v1"

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )

            latency = (time.time() - start_time) * 1000

            if response.status_code != 200:
                raise RuntimeError(f"LiteLLM API error: {response.status_code} - {response.text}")

            data = response.json()

            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data.get("model", params["model"]),
                provider=self.get_provider_name(),
                tokens_used=data.get("usage", {}).get("total_tokens"),
                cost_usd=data.get("usage", {}).get("cost"),
                latency_ms=latency
            )

        except ImportError:
            return await self._complete_with_litellm(prompt, config)

    async def _complete_with_litellm(self, prompt: str, config: Optional[LLMConfig] = None) -> LLMResponse:
        try:
            import litellm
            params = self._get_litellm_params(config)

            start_time = time.time()
            response = await litellm.acompletion(
                messages=[{"role": "user", "content": prompt}],
                **params
            )
            latency = (time.time() - start_time) * 1000

            return LLMResponse(
                content=response["choices"][0]["message"]["content"],
                model=response.get("model", params["model"]),
                provider=self.get_provider_name(),
                tokens_used=response.get("usage", {}).get("total_tokens"),
                cost_usd=response.get("usage", {}).get("cost"),
                latency_ms=latency
            )
        except ImportError:
            raise RuntimeError(
                "LiteLLM not installed. Install with: pip install litellm "
                "or use httpx-based fallback mode."
            )

    async def complete_structured(
        self,
        prompt: str,
        schema: dict,
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        import httpx

        cfg = config or LLMConfig(model=self.model)

        structured_prompt = f"""{prompt}

Respond ONLY with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

JSON Response:"""

        params = self._get_litellm_params(cfg)
        params["temperature"] = 0.1

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": params["model"],
            "messages": [{"role": "user", "content": structured_prompt}],
            "temperature": params["temperature"],
            "max_tokens": params["max_tokens"],
            "response_format": {"type": "json_object"}
        }

        base_url = params.get("api_base", "https://llm.api.ai-code-reviewer.dev/v1")

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )

            latency = (time.time() - start_time) * 1000

            if response.status_code != 200:
                raise RuntimeError(f"LiteLLM API error: {response.status_code}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            try:
                json.loads(content)
            except json.JSONDecodeError:
                raise RuntimeError("Response is not valid JSON")

            return LLMResponse(
                content=content,
                model=data.get("model", params["model"]),
                provider=self.get_provider_name(),
                tokens_used=data.get("usage", {}).get("total_tokens"),
                cost_usd=data.get("usage", {}).get("cost"),
                latency_ms=latency
            )

        except ImportError:
            return await self._complete_structured_with_litellm(prompt, schema, config)

    async def _complete_structured_with_litellm(
        self,
        prompt: str,
        schema: dict,
        config: Optional[LLMConfig] = None
    ) -> LLMResponse:
        try:
            import litellm
            params = self._get_litellm_params(config)
            params["temperature"] = 0.1
            params["response_format"] = {"type": "json_object"}

            structured_prompt = f"""{prompt}

Respond ONLY with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

JSON Response:"""

            start_time = time.time()
            response = await litellm.acompletion(
                messages=[{"role": "user", "content": structured_prompt}],
                **params
            )
            latency = (time.time() - start_time) * 1000

            content = response["choices"][0]["message"]["content"]

            try:
                json.loads(content)
            except json.JSONDecodeError:
                raise RuntimeError("Response is not valid JSON")

            return LLMResponse(
                content=content,
                model=response.get("model", params["model"]),
                provider=self.get_provider_name(),
                tokens_used=response.get("usage", {}).get("total_tokens"),
                cost_usd=response.get("usage", {}).get("cost"),
                latency_ms=latency
            )
        except ImportError:
            raise RuntimeError("LiteLLM not installed")


def create_litellm_adapter(
    provider: str = None,
    model: str = None,
    api_key: str = None,
    base_url: str = None,
) -> LiteLLMAdapter:
    """Factory function to create LiteLLM adapter with provider-specific defaults."""
    return LiteLLMAdapter(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )
