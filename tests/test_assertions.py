"""Pure-logic tests for the assertion engine. No network, no API keys needed."""
import os

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("OPENROUTER_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")

from prompt_eval.schemas import (
    ContainsCriterion,
    JsonFieldCriterion,
    LengthCriterion,
    NotContainsCriterion,
    RangeCriterion,
)
from prompt_eval.service import PromptEvalService
from prompt_eval.utils.json_parser import extract_json_from_llm_response


@pytest.fixture
def service() -> PromptEvalService:
    return PromptEvalService()


class TestJsonFieldAssertion:
    def test_pass(self, service):
        result = service._assert_json_field(
            JsonFieldCriterion(field="sentiment", equals="positive"),
            {"sentiment": "positive"},
        )
        assert result.passed

    def test_value_mismatch(self, service):
        result = service._assert_json_field(
            JsonFieldCriterion(field="sentiment", equals="positive"),
            {"sentiment": "negative"},
        )
        assert not result.passed

    def test_missing_field(self, service):
        result = service._assert_json_field(
            JsonFieldCriterion(field="sentiment", equals="positive"),
            {"other": "value"},
        )
        assert not result.passed
        assert "없습니다" in result.detail[0]

    def test_response_not_json(self, service):
        result = service._assert_json_field(
            JsonFieldCriterion(field="sentiment", equals="positive"),
            None,
        )
        assert not result.passed


class TestRangeAssertion:
    def test_in_range(self, service):
        result = service._assert_range(
            RangeCriterion(field="score", min=0.0, max=1.0),
            {"score": 0.7},
        )
        assert result.passed

    def test_out_of_range(self, service):
        result = service._assert_range(
            RangeCriterion(field="score", min=0.0, max=1.0),
            {"score": 1.5},
        )
        assert not result.passed

    def test_non_numeric(self, service):
        result = service._assert_range(
            RangeCriterion(field="score", min=0.0, max=1.0),
            {"score": "high"},
        )
        assert not result.passed


class TestContainsAssertion:
    def test_all_present(self, service):
        result = service._assert_contains(
            ContainsCriterion(values=["sorry", "10%"]),
            "I'm sorry — here's a 10% coupon.",
        )
        assert result.passed

    def test_one_missing(self, service):
        result = service._assert_contains(
            ContainsCriterion(values=["sorry", "10%"]),
            "I'm sorry — please try again.",
        )
        assert not result.passed
        assert "10%" in result.detail[0]


class TestNotContainsAssertion:
    def test_forbidden_absent(self, service):
        result = service._assert_not_contains(
            NotContainsCriterion(values=["unfortunately"]),
            "Sorry, here's a coupon.",
        )
        assert result.passed

    def test_forbidden_present(self, service):
        result = service._assert_not_contains(
            NotContainsCriterion(values=["unfortunately"]),
            "unfortunately we cannot help.",
        )
        assert not result.passed

    def test_case_sensitive(self, service):
        result = service._assert_not_contains(
            NotContainsCriterion(values=["unfortunately"]),
            "Unfortunately we cannot help.",
        )
        assert result.passed, "matching is case-sensitive by design"


class TestLengthAssertion:
    def test_within_max(self, service):
        result = service._assert_length(
            LengthCriterion(max=10),
            "hello",
        )
        assert result.passed

    def test_over_max(self, service):
        result = service._assert_length(
            LengthCriterion(max=3),
            "hello",
        )
        assert not result.passed

    def test_under_min(self, service):
        result = service._assert_length(
            LengthCriterion(min=10),
            "hello",
        )
        assert not result.passed


class TestJsonParser:
    def test_plain_json(self):
        assert extract_json_from_llm_response('{"a": 1}') == {"a": 1}

    def test_fenced_json(self):
        text = 'Here is the result:\n```json\n{"a": 1}\n```'
        assert extract_json_from_llm_response(text) == {"a": 1}

    def test_embedded_json(self):
        text = 'The answer is {"a": 1} as shown.'
        assert extract_json_from_llm_response(text) == {"a": 1}

    def test_invalid(self):
        assert extract_json_from_llm_response("not json at all") is None


class TestScoreCalc:
    def test_empty(self, service):
        assert service._calc_score([]) == 0.0

    def test_all_pass(self, service):
        from prompt_eval.schemas import AssertionResult

        results = [
            AssertionResult(type="contains", passed=True, detail=["ok"]),
            AssertionResult(type="length", passed=True, detail=["ok"]),
        ]
        assert service._calc_score(results) == 100.0

    def test_mixed_with_judge(self, service):
        from prompt_eval.schemas import AssertionResult

        results = [
            AssertionResult(type="contains", passed=True, detail=["ok"]),
            AssertionResult(type="llm_judge", passed=False, detail=["ok"], score=60.0),
        ]
        assert service._calc_score(results) == 80.0
