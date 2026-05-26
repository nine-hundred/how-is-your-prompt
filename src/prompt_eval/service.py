import logging
from typing import Optional

from prompt_eval.providers.claude import ClaudeService
from prompt_eval.providers.gemini import GeminiService
from prompt_eval.providers.openrouter import OpenRouterService
from prompt_eval.schemas import (
    AssertionResult,
    ContainsCriterion,
    EvalCriterion,
    EvalProvider,
    JsonFieldCriterion,
    LengthCriterion,
    LlmJudgeCriterion,
    NotContainsCriterion,
    PromptEvalRunRequest,
    PromptEvalRunResponse,
    RangeCriterion,
)
from prompt_eval.utils.json_parser import extract_json_from_llm_response

logger = logging.getLogger(__name__)

_JUDGE_PROMPT_TEMPLATE = """\
아래는 원본 프롬프트와 LLM이 생성한 응답입니다. 주어진 평가 기준에 따라 1~100점으로 채점하세요.

[원본 프롬프트]
{original_prompt}

[LLM 응답]
{response}

[평가 기준]
{rubric}

반드시 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.
{{"score": 점수, "reason": "한 줄 이유"}}"""


class PromptEvalService:

    def __init__(self):
        self._claude: Optional[ClaudeService] = None
        self._openrouter: Optional[OpenRouterService] = None
        self._gemini: Optional[GeminiService] = None

    def _get_claude(self) -> ClaudeService:
        if self._claude is None:
            self._claude = ClaudeService()
        return self._claude

    def _get_openrouter(self) -> OpenRouterService:
        if self._openrouter is None:
            self._openrouter = OpenRouterService()
        return self._openrouter

    def _get_gemini(self) -> GeminiService:
        if self._gemini is None:
            self._gemini = GeminiService()
        return self._gemini

    async def run(self, request: PromptEvalRunRequest) -> PromptEvalRunResponse:
        raw_response = await self._call_llm(request.prompt, request.provider, request.model)

        parsed: Optional[dict] = extract_json_from_llm_response(raw_response)

        assertion_results: list[AssertionResult] = []
        for criterion in request.eval_criteria:
            result = await self._run_assertion(criterion, raw_response, parsed, request.prompt)
            assertion_results.append(result)

        passed = all(r.passed for r in assertion_results)
        score = self._calc_score(assertion_results)

        return PromptEvalRunResponse(
            raw_response=raw_response,
            passed=passed,
            score=score,
            assertions=assertion_results,
        )

    async def _call_llm(self, prompt: str, provider: EvalProvider, model: Optional[str] = None) -> str:
        if provider == EvalProvider.CLAUDE:
            return await self._get_claude().call(prompt, model=model)
        elif provider == EvalProvider.OPENROUTER:
            return await self._get_openrouter().call(prompt, model=model)
        elif provider == EvalProvider.GEMINI:
            return await self._get_gemini().call(prompt, model=model)
        raise ValueError(f"지원하지 않는 프로바이더: {provider}")

    async def _call_judge(self, original_prompt: str, response_text: str, rubric: str, judge_provider: EvalProvider, judge_model: Optional[str] = None) -> tuple[int, str]:
        judge_prompt = _JUDGE_PROMPT_TEMPLATE.format(
            original_prompt=original_prompt,
            response=response_text,
            rubric=rubric,
        )
        try:
            raw = await self._call_llm(judge_prompt, judge_provider, model=judge_model)
        except Exception as e:
            logger.error(f"Judge LLM 호출 실패: {e}")
            return 0, f"Judge LLM 호출 실패: {e}"

        data = extract_json_from_llm_response(raw)
        if data:
            return int(data.get("score", 0)), str(data.get("reason", ""))
        logger.warning(f"Judge 응답 파싱 실패: {raw}")
        return 0, f"Judge 응답 파싱 실패: {raw[:200]}"

    async def _run_assertion(
        self,
        criterion: EvalCriterion,
        raw_response: str,
        parsed: Optional[dict],
        original_prompt: str,
    ) -> AssertionResult:
        if isinstance(criterion, JsonFieldCriterion):
            return self._assert_json_field(criterion, parsed)
        elif isinstance(criterion, RangeCriterion):
            return self._assert_range(criterion, parsed)
        elif isinstance(criterion, ContainsCriterion):
            return self._assert_contains(criterion, raw_response)
        elif isinstance(criterion, NotContainsCriterion):
            return self._assert_not_contains(criterion, raw_response)
        elif isinstance(criterion, LengthCriterion):
            return self._assert_length(criterion, raw_response)
        elif isinstance(criterion, LlmJudgeCriterion):
            return await self._assert_llm_judge(criterion, original_prompt, raw_response)
        raise ValueError(f"알 수 없는 criterion 타입: {type(criterion)}")

    def _assert_json_field(self, c: JsonFieldCriterion, parsed: Optional[dict]) -> AssertionResult:
        if parsed is None:
            return AssertionResult(
                type="json_field",
                passed=False,
                detail=[f"응답이 JSON이 아닙니다. field='{c.field}'"],
            )
        actual = parsed.get(c.field, "__MISSING__")
        if actual == "__MISSING__":
            return AssertionResult(
                type="json_field",
                passed=False,
                detail=[f"field '{c.field}'가 응답에 없습니다."],
            )
        passed = actual == c.equals
        return AssertionResult(
            type="json_field",
            passed=passed,
            detail=[f"field '{c.field}': 기대={c.equals}, 실제={actual}"],
        )

    def _assert_range(self, c: RangeCriterion, parsed: Optional[dict]) -> AssertionResult:
        if parsed is None:
            return AssertionResult(
                type="range",
                passed=False,
                detail=[f"응답이 JSON이 아닙니다. field='{c.field}'"],
            )
        actual = parsed.get(c.field)
        if actual is None:
            return AssertionResult(
                type="range",
                passed=False,
                detail=[f"field '{c.field}'가 응답에 없습니다."],
            )
        try:
            val = float(actual)
        except (TypeError, ValueError):
            return AssertionResult(
                type="range",
                passed=False,
                detail=[f"field '{c.field}' 값이 숫자가 아닙니다: {actual}"],
            )
        passed = c.min <= val <= c.max
        return AssertionResult(
            type="range",
            passed=passed,
            detail=[f"field '{c.field}': 범위={c.min}~{c.max}, 실제={val}"],
        )

    def _assert_contains(self, c: ContainsCriterion, raw: str) -> AssertionResult:
        missing = [v for v in c.values if v not in raw]
        passed = len(missing) == 0
        detail = ["모두 포함됨"] if passed else [f"누락: {missing}"]
        return AssertionResult(type="contains", passed=passed, detail=detail)

    def _assert_not_contains(self, c: NotContainsCriterion, raw: str) -> AssertionResult:
        found = [v for v in c.values if v in raw]
        passed = len(found) == 0
        detail = ["금지 문자열 없음"] if passed else [f"발견된 금지 문자열: {found}"]
        return AssertionResult(type="not_contains", passed=passed, detail=detail)

    def _assert_length(self, c: LengthCriterion, raw: str) -> AssertionResult:
        length = len(raw)
        passed = True
        if c.min is not None and length < c.min:
            passed = False
        if c.max is not None and length > c.max:
            passed = False
        summary = f"글자 수={length}"
        if c.min is not None:
            summary += f", 최소={c.min}"
        if c.max is not None:
            summary += f", 최대={c.max}"
        return AssertionResult(type="length", passed=passed, detail=[summary])

    async def _assert_llm_judge(self, c: LlmJudgeCriterion, original_prompt: str, raw: str) -> AssertionResult:
        scores = []
        reasons = []
        for _ in range(c.repeat):
            score, reason = await self._call_judge(original_prompt, raw, c.rubric, c.judge_provider, c.judge_model)
            scores.append(score)
            reasons.append(reason)

        avg_score = round(sum(scores) / len(scores), 1)
        passed = avg_score >= c.min_score

        if c.repeat > 1:
            detail = [f"점수={avg_score}/100, 기준={c.min_score}/100 (총 {c.repeat}회 평균)"]
            for i, (s, r) in enumerate(zip(scores, reasons), 1):
                detail.append(f"{i}회: {s}점 | {r}")
        else:
            detail = [f"점수={avg_score}/100, 기준={c.min_score}/100", reasons[0]]

        return AssertionResult(
            type="llm_judge",
            passed=passed,
            detail=detail,
            score=avg_score,
        )

    def _calc_score(self, results: list[AssertionResult]) -> float:
        if not results:
            return 0.0

        total = 0.0
        for r in results:
            if r.type == "llm_judge" and r.score is not None:
                total += r.score
            else:
                total += 100.0 if r.passed else 0.0

        return round(total / len(results), 1)
