from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    default_model: str

    async def call(self, prompt: str, model: Optional[str] = None) -> str: ...
