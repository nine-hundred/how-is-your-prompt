"""Expose prompt_eval as an HTTP API (single-file demo).

    uv run uvicorn examples.api_server:app --reload

Then:
    curl -X POST http://localhost:8000/eval/run \
      -H 'Content-Type: application/json' \
      -d @examples/sample_request.json
"""
from fastapi import FastAPI

from prompt_eval import (
    PromptEvalRunRequest,
    PromptEvalRunResponse,
    PromptEvalService,
)

app = FastAPI(title="prompt-eval", version="0.1.0")
service = PromptEvalService()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/eval/run", response_model=PromptEvalRunResponse)
async def run_eval(request: PromptEvalRunRequest) -> PromptEvalRunResponse:
    return await service.run(request)
