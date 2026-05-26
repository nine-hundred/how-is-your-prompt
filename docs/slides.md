# 여러분의 프롬프트는 안녕하신가요?

> 사내 발표(2026-05)의 공개 버전 아웃라인. 원본 슬라이드는 사내 제품 예제를 사용해서 공개하지 않습니다.
> 이 문서는 그대로 슬라이드 도구(Keynote / Google Slides / Marp 등)로 옮길 수 있도록 한 페이지 = 한 슬라이드 단위로 구성되어 있습니다.

---

## 1. 표지

> 👋 **여러분의 프롬프트는 안녕하신가요?**
>
> *prompt-eval — 프롬프트를 코드처럼 평가하기*

---

## 2. 문제 / 해결 / 시연

### 우리가 프롬프트를 개선할 때 어떻게 확인했나요?

- 확인 방식은 단순했습니다.
- Claude나 Grok 브라우저를 열고, 프롬프트를 붙여넣고, 직접 눈으로 보는 것.
- 케이스가 여러 개면 하나씩 반복합니다.

### 문제

> 프롬프트가 좋아졌는지 나빠졌는지, 지금까지는 측정하는 방법이 없었어요.

- 테스트 케이스가 늘어날수록 / 마음에 들지 않는 결과물이 나타날수록 수작업 반복이 많아집니다.
- 품질에 대한 기준이 달라 의사결정이 어렵습니다.
- "이게 더 나은 것 같은데" — 결국 감으로 판단하게 됩니다.

### 해결

- 프롬프트를 입력하면 LLM을 실제로 호출하고,
- 응답을 사전에 정의한 기준으로 자동 평가하는 기능을 만들었습니다.
- 각 프롬프트별 평가 방법이 다르기에, 동적으로 적용할 수 있도록 설계했습니다.
- 비개발자도 직접 프롬프트를 테스트하고 정량적인 점수를 확인할 수 있도록 합니다.

> 참고: [LLM-as-a-Judge survey (arXiv:2411.15594)](https://arxiv.org/pdf/2411.15594)

---

## 3. 시연 — EX1: JSON 형태 검증 (감정 분류)

### Request

```json
{
  "prompt": "Classify the sentiment of the review below.\nReturn ONLY JSON: {\"sentiment\": \"positive\"|\"negative\"|\"neutral\", \"confidence\": 0.0-1.0}\n\nReview: \"The food arrived cold and the staff was rude.\"",
  "provider": "openrouter",
  "model": "openai/gpt-4o-mini",
  "eval_criteria": [
    { "type": "json_field", "field": "sentiment", "equals": "negative" },
    { "type": "range",      "field": "confidence", "min": 0.0, "max": 1.0 }
  ]
}
```

### Response

```json
{
  "raw_response": "{\"sentiment\": \"negative\", \"confidence\": 0.92}",
  "passed": true,
  "score": 100.0,
  "assertions": [
    { "type": "json_field", "passed": true, "detail": ["field 'sentiment': 기대=negative, 실제=negative"] },
    { "type": "range",      "passed": true, "detail": ["field 'confidence': 범위=0.0~1.0, 실제=0.92"] }
  ]
}
```

> 포인트: **결정적 기준 두 줄로 "이 프롬프트가 의도한 스키마를 지키는가"를 회귀 테스트로 박제**할 수 있습니다.

---

## 4. 시연 — EX2: LLM-as-Judge (코드 리뷰 톤)

### Request

```json
{
  "prompt": "Review the following Python function and suggest improvements.\n\ndef add(a, b):\n    return a + b",
  "provider": "openrouter",
  "model": "openai/gpt-4o-mini",
  "eval_criteria": [
    {
      "type": "llm_judge",
      "judge_provider": "openrouter",
      "judge_model": "openai/gpt-4o-mini",
      "repeat": 2,
      "min_score": 70,
      "rubric": "0-100점으로 채점:\n- 타입 힌트 누락 지적 (40점)\n- 도크스트링/입력 검증 언급 (30점)\n- 건설적인 톤, 트집 잡지 않음 (30점)"
    }
  ]
}
```

### Response

```json
{
  "raw_response": "이 함수는 매우 단순하지만 다음을 개선하면 좋겠습니다:\n1. 타입 힌트 (`a: int, b: int -> int`)\n2. 도크스트링 추가\n3. 입력 타입 검증 ...",
  "passed": true,
  "score": 84.0,
  "assertions": [
    {
      "type": "llm_judge",
      "passed": true,
      "score": 84.0,
      "detail": [
        "점수=84.0/100, 기준=70/100 (총 2회 평균)",
        "1회: 85점 | 타입 힌트, 도크스트링 모두 지적했고 톤이 건설적임",
        "2회: 83점 | 같은 항목 커버, 입력 검증 언급은 부드러움"
      ]
    }
  ]
}
```

> 포인트: 결정적 기준으로는 잡을 수 없는 **"톤"** 같은 정성 항목을 다른 LLM이 rubric으로 채점합니다. `repeat: 2`로 흔들림을 평균냅니다.

---

## 5. 주의사항

### 평가 기준(rubric)을 구체적으로 작성할수록 점수도 안정됩니다

- "좋은 응답인가?"보다 "캐릭터 설정에 맞는 말투를 사용하고 있는가?"처럼 구체적인 기준이 Judge에 적힌 일관성을 높입니다.

### 검증 점수가 맞을수록 정확도가 높아집니다

- LLM 응답이 매번 조금씩 달라집니다. 한 번 실행한 결과만으로 판단하지 말고, 동일한 프롬프트를 여러 번 실행(`repeat`)해서 점수의 평균과 분포를 보는 것이 좋습니다.

### 점수는 절대값이 아닌 상대값으로 봐야 합니다

- 특정 점수(예: 83점)가 "좋은 프롬프트"를 의미하지는 않습니다. 같은 기준으로 A 버전과 B 버전을 비교했을 때 어느 쪽이 높은지를 보는 것이 의미가 있습니다.

### 평가 대상 모델과 Judge 모델은 달라야 합니다

- Claude로 생성한 응답을 Claude가 채점하면 자기 응답에 후한 점수를 줄 수 있습니다. 한쪽이 이슈를 그려내면 Judge는 별도 모델을 사용하는 것이 권장됩니다.

### Judge 모델이 충분히 강한 모델을 사용하세요

- Judge는 응답이 좋고 나쁨을 *이해해야 판단*이 가능합니다. (예: `gemini-2.5-pro`, `claude-opus-4-7`) 등 평가 모델보다 상위 모델을 Judge로 설정하는 것을 권장합니다.