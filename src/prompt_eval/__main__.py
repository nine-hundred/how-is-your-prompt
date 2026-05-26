import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter, ValidationError

from prompt_eval.schemas import (
    AssertionResult,
    EvalCriterion,
    PromptEvalRunRequest,
    PromptEvalRunResponse,
)
from prompt_eval.service import PromptEvalService

_criteria_adapter = TypeAdapter(list[EvalCriterion])


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m"


def _red(text: str) -> str:
    return f"\033[31m{text}\033[0m"


def _dim(text: str) -> str:
    return f"\033[2m{text}\033[0m"


def _format_assertion(a: AssertionResult) -> str:
    mark = _green("PASS") if a.passed else _red("FAIL")
    lines = [f"  {mark} [{a.type}] {a.detail[0] if a.detail else ''}"]
    for extra in a.detail[1:]:
        lines.append(_dim(f"       {extra}"))
    return "\n".join(lines)


def _format_response(name: str, response: PromptEvalRunResponse) -> str:
    header = _bold(f"== {name} ==")
    summary_mark = _green("PASSED") if response.passed else _red("FAILED")
    summary = f"  {summary_mark}  score={response.score}"
    body = "\n".join(_format_assertion(a) for a in response.assertions)
    preview = _dim(f"  response: {response.raw_response[:120].replace(chr(10), ' ')}...")
    return "\n".join([header, summary, body, preview])


def _load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "cases" not in data:
        raise ValueError(f"{path}: top-level 'cases' list is required")
    cases = data["cases"]
    if not isinstance(cases, list):
        raise ValueError(f"{path}: 'cases' must be a list")
    return cases


def _build_request(case: dict[str, Any]) -> PromptEvalRunRequest:
    raw_criteria = case.get("eval_criteria", [])
    try:
        criteria = _criteria_adapter.validate_python(raw_criteria)
    except ValidationError as e:
        raise ValueError(f"invalid eval_criteria in case '{case.get('name', '?')}': {e}") from e
    return PromptEvalRunRequest(
        prompt=case["prompt"],
        provider=case["provider"],
        model=case.get("model"),
        eval_criteria=criteria,
    )


async def _run_cases(path: Path) -> int:
    cases = _load_cases(path)
    service = PromptEvalService()

    failures = 0
    for idx, case in enumerate(cases, 1):
        name = case.get("name", f"case-{idx}")
        try:
            request = _build_request(case)
        except (KeyError, ValueError) as e:
            print(_red(f"== {name} ==\n  CONFIG ERROR: {e}"))
            failures += 1
            continue

        try:
            response = await service.run(request)
        except Exception as e:
            print(_red(f"== {name} ==\n  RUN ERROR: {e}"))
            failures += 1
            continue

        print(_format_response(name, response))
        if not response.passed:
            failures += 1
        print()

    total = len(cases)
    summary = f"{total - failures}/{total} passed"
    print(_bold(_green(summary) if failures == 0 else _red(summary)))
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m prompt_eval",
        description="Run prompt evaluation cases from a YAML file.",
    )
    parser.add_argument("cases", type=Path, help="Path to a YAML cases file")
    args = parser.parse_args()

    if not args.cases.exists():
        print(_red(f"file not found: {args.cases}"), file=sys.stderr)
        return 2

    return asyncio.run(_run_cases(args.cases))


if __name__ == "__main__":
    sys.exit(main())
