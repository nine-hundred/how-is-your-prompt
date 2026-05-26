import os
from typing import Optional

from openai import AsyncOpenAI


class OpenRouterService:
    default_model = "openai/gpt-4o-mini"

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        self._client = AsyncOpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
        )

    async def call(self, prompt: str, model: Optional[str] = None) -> str:
        completion = await self._client.chat.completions.create(
            model=model or self.default_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content or ""
