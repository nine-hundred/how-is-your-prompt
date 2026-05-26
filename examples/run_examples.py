"""Use prompt_eval as a library (no YAML).

    python examples/run_examples.py
"""
import asyncio

from prompt_eval import (
    EvalProvider,
    JsonFieldCriterion,
    LlmJudgeCriterion,
    PromptEvalRunRequest,
    PromptEvalService,
    RangeCriterion,
)


async def main() -> None:
    service = PromptEvalService()

    request = PromptEvalRunRequest(
        prompt=(
            'Classify sentiment. Return ONLY JSON: '
            '{"sentiment": "positive"|"negative"|"neutral", "confidence": 0.0-1.0}\n\n'
            'Review: "The food arrived cold and the staff was rude."'
        ),
        provider=EvalProvider.OPENROUTER,
        model="openai/gpt-4o-mini",
        eval_criteria=[
            JsonFieldCriterion(field="sentiment", equals="negative"),
            RangeCriterion(field="confidence", min=0.0, max=1.0),
            LlmJudgeCriterion(
                rubric="The response must be a single JSON object with no prose.",
                min_score=80,
                judge_provider=EvalProvider.OPENROUTER,
                judge_model="openai/gpt-4o-mini",
            ),
        ],
    )

    response = await service.run(request)

    print(f"passed: {response.passed}")
    print(f"score:  {response.score}")
    for a in response.assertions:
        mark = "PASS" if a.passed else "FAIL"
        print(f"  [{mark}] {a.type}: {a.detail[0]}")


if __name__ == "__main__":
    asyncio.run(main())
