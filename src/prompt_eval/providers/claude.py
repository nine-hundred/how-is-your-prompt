import os
from typing import Optional

from anthropic import AsyncAnthropic


class ClaudeService:
    default_model = "claude-sonnet-4-6"

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._client = AsyncAnthropic(api_key=key)

    async def call(self, prompt: str, model: Optional[str] = None) -> str:
        message = await self._client.messages.create(
            model=model or self.default_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        chunks: list[str] = []
        for block in message.content:
            if getattr(block, "type", None) == "text":
                chunks.append(block.text)
        return "".join(chunks)
