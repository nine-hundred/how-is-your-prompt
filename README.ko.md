# prompt-eval

## 개요
LLM 프롬프트를 결정적 assertion과 LLM-as-Judge로 자동 평가하는 작은 선언형 프레임워크입니다. 

사내 발표 **"여러분의 프롬프트는 안녕하신가요?"** 에서 시연했던 코드를 정리하고 공개 버전으로 확장한 프로젝트입니다.

[English README →](./README.md) · [발표 아웃라인 →](./docs/slides.md)

<p align="center">
  <img src="./docs/images/01-cover.png" alt="발표 표지" width="420">
</p>

## 시작 배경
프롬프트를 개선할 때 우리가 확인했던 방식은 단순했습니다. 브라우저를 열고, 프롬프트를 붙여넣고, 응답을 눈으로 읽어보는 것. 케이스가 늘어나면 그만큼 반복합니다.

이렇게 하니 "이게 더 나아진 건가?"라는 질문에 답할 방법이 없었습니다. 기준이 사람마다 다르고, 같은 사람도 어제와 오늘이 다르고, 결국 감으로 판단하게 됩니다. 모델을 바꾸거나 프롬프트를 손볼 때마다 회귀를 잡아줄 그물이 없었던 거죠.

그래서 프롬프트를 코드처럼 다룰 방법을 만들었습니다. *좋은 응답*이 무엇인지 선언하고, 실제로 LLM을 호출하고, 사전에 정의한 기준으로 점수를 받습니다. 정성 평가는 [LLM-as-a-Judge](https://arxiv.org/pdf/2411.15594) 패턴으로 다른 LLM에게 채점을 맡깁니다.

## 설계 방향
### 선언형 평가 기준
각 프롬프트마다 검증하고 싶은 항목이 다릅니다. JSON 스키마 검증이 필요한 곳이 있고, 금칙어 체크가 필요한 곳이 있고, "톤이 적절한가" 같은 정성 평가가 필요한 곳도 있습니다. 평가 방식을 코드에 박지 않고 케이스마다 선언할 수 있도록 [discriminated union](./src/prompt_eval/schemas.py)으로 6가지 기준을 정의했습니다.

| 기준 | 검증 내용 |
|---|---|
| `json_field` | 응답이 JSON이고 특정 필드가 기대값과 같은지 |
| `range` | JSON 숫자 필드가 `[min, max]` 범위 안인지 |
| `contains` / `not_contains` | 응답에 특정 문자열이 있거나/없는지 |
| `length` | 응답 길이가 범위 안인지 |
| `llm_judge` | 별도 judge LLM이 rubric으로 0–100점 채점 (`repeat`로 평균) |

### CI에 붙일 수 있는 형태
yaml로 케이스를 선언하면 `python -m prompt_eval cases.yaml` 한 줄로 돌릴 수 있고, 실패하면 exit code가 0이 아닙니다. 그대로 GitHub Actions에 붙여 프롬프트 회귀 테스트로 사용할 수 있습니다.

### 프로바이더는 지연 인스턴스화
Claude, Gemini, OpenRouter 세 가지를 지원하지만 케이스에서 실제로 사용하는 프로바이더만 초기화합니다. 키 하나만 있어도 시작할 수 있습니다.

## 사용 예시
### YAML로 케이스 선언
```yaml
cases:
  - name: customer_reply_tone
    provider: openrouter
    model: openai/gpt-4o-mini
    prompt: |
      배송 지연에 항의하는 고객에게 짧은 답장을 작성하세요 (300자 이내).
      사과와 함께 10% 쿠폰을 제안하세요.
      "unfortunately"와 "policy"라는 단어는 사용하지 마세요.
    eval_criteria:
      - type: not_contains
        values: ["unfortunately", "policy"]
      - type: contains
        values: ["10%"]
      - type: length
        max: 300
```

```bash
python -m prompt_eval examples/cases.yaml
```

```
== sentiment_classifier_json_shape ==
  PASSED  score=100.0
  PASS [json_field] field 'sentiment': 기대=negative, 실제=negative
  PASS [range]      field 'confidence': 범위=0.0~1.0, 실제=0.85

3/3 passed
```

### 라이브러리로 호출
```python
import asyncio
from prompt_eval import (
    EvalProvider, JsonFieldCriterion, PromptEvalRunRequest, PromptEvalService,
)

async def main():
    service = PromptEvalService()
    response = await service.run(PromptEvalRunRequest(
        prompt='ONLY JSON으로만 응답: {"intent": "refund"|"shipping"|"other"}\n\n메시지: "내 주문은 어디 있죠?"',
        provider=EvalProvider.OPENROUTER,
        model="openai/gpt-4o-mini",
        eval_criteria=[JsonFieldCriterion(field="intent", equals="shipping")],
    ))
    print(response.passed, response.score)

asyncio.run(main())
```

### HTTP API로 호출
사내 발표에서 시연했던 형태 그대로 단일 파일 FastAPI 서버를 포함시켰습니다.

```bash
.venv/bin/uvicorn examples.api_server:app --reload

curl -X POST http://localhost:8000/eval/run \
  -H 'Content-Type: application/json' \
  -d @examples/sample_request.json
```

## 시작하기
```bash
git clone <레포 주소>
cd how-is-your-prompt
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api,dev]"
cp .env.example .env   # 최소 하나의 프로바이더 키 입력
python -m prompt_eval examples/cases.yaml
```

테스트는 assertion 엔진과 JSON 파서를 검증하므로 네트워크 호출 없이 돌아갑니다.

```bash
.venv/bin/pytest
```

## 기술 스택
### Core
- Python 3.10+ - `asyncio` 기반
- Pydantic v2 - discriminated union으로 평가 기준 선언

### Providers
- Anthropic (Claude) / Google (Gemini) / OpenRouter

### Surface
- Click-free CLI (`python -m prompt_eval`) - CI에 그대로 연결
- FastAPI - 사내 데모와 동일한 HTTP 형태

## 참고 자료
- **[LLM-as-a-Judge: A Survey (arXiv:2411.15594)](https://arxiv.org/pdf/2411.15594)** - judge 패턴 전반에 대한 서베이
- **[promptfoo](https://www.promptfoo.dev/)** / **[deepeval](https://github.com/confident-ai/deepeval)** - 같은 문제를 푸는 더 큰 프레임워크들
