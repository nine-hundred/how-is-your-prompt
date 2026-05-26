import os
from typing import Optional

from google import genai


class GeminiService:
    default_model = "gemini-2.5-flash"

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self._client = genai.Client(api_key=key)

    async def call(self, prompt: str, model: Optional[str] = None) -> str:
        response = await self._client.aio.models.generate_content(
            model=model or self.default_model,
            contents=prompt,
        )
        return response.text or ""
