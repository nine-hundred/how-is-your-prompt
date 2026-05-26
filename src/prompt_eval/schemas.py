from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class EvalProvider(str, Enum):
    CLAUDE = "claude"
    OPENROUTER = "openrouter"
    GEMINI = "gemini"


class JsonFieldCriterion(BaseModel):
    type: Literal["json_field"] = "json_field"
    field: str
    equals: Any


class RangeCriterion(BaseModel):
    type: Literal["range"] = "range"
    field: str
    min: float
    max: float


class ContainsCriterion(BaseModel):
    type: Literal["contains"] = "contains"
    values: list[str]


class NotContainsCriterion(BaseModel):
    type: Literal["not_contains"] = "not_contains"
    values: list[str]


class LengthCriterion(BaseModel):
    type: Literal["length"] = "length"
    min: Optional[int] = None
    max: Optional[int] = None


class LlmJudgeCriterion(BaseModel):
    type: Literal["llm_judge"] = "llm_judge"
    rubric: str
    min_score: int = Field(ge=0, le=100)
    judge_provider: EvalProvider
    judge_model: Optional[str] = None
    repeat: int = Field(default=1, ge=1, le=10)


EvalCriterion = Annotated[
    Union[
        JsonFieldCriterion,
        RangeCriterion,
        ContainsCriterion,
        NotContainsCriterion,
        LengthCriterion,
        LlmJudgeCriterion,
    ],
    Field(discriminator="type"),
]


class PromptEvalRunRequest(BaseModel):
    prompt: str
    provider: EvalProvider
    model: Optional[str] = None
    eval_criteria: list[EvalCriterion] = Field(default_factory=list)


class AssertionResult(BaseModel):
    type: str
    passed: bool
    detail: list[str]
    score: Optional[float] = None


class PromptEvalRunResponse(BaseModel):
    raw_response: str
    passed: bool
    score: float
    assertions: list[AssertionResult]
