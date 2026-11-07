# chatbot-politics

정치 토론 시뮬레이션 챗봇. 사용자가 토론 주제와 찬성/반대 입장을 정하면, 챗봇이 반대편을 맡아
[토론 규칙](docs/DEBATE_RULES.md)에 따라 토론을 진행한다. OpenAI Responses API와 웹 검색 도구를
사용해 법령·통계·기사를 찾아 근거로 쓴다.

## 기능

- 정해진 토론 형식(입론 → 교차조사 → 반론 → 최종변론 → 정리)을 단계별로 진행
- 챗봇은 법령·기사 등을 웹 검색으로 확인하고 근거 등급(`[법령]`, `[공식통계]`, `[학술]`, `[언론]`, `[주장]`, `[불확실]`)과 출처를 표기
- 사용자는 자기 차례 전에 자료를 요청해 근거로 정리받을 수 있음
- 토론 단계 발언에서 완충 표현이 감지되면 자동으로 다시 씀 (규칙 제5장)
- 토론 종료 후 양측 근거별 피드백, 쟁점 요약, 근거의 공백 제시

## 실행

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # OPENAI_API_KEY 입력
.venv/bin/streamlit run app.py
```

`.env`의 `OPENAI_MODEL`로 모델을 바꿀 수 있다 (웹 검색 도구를 지원하는 모델이어야 한다).

## 구조

| 파일 | 역할 |
|---|---|
| [docs/DEBATE_RULES.md](docs/DEBATE_RULES.md) | 토론 규칙. 실행 시 그대로 시스템 지시문이 된다. |
| [docs/RULE_ENFORCEMENT.md](docs/RULE_ENFORCEMENT.md) | 각 규칙을 코드에서 어떻게 적용했는지와 한계 |
| [debate_bot/debate_format.py](debate_bot/debate_format.py) | 토론 단계 정의 (규칙 제2장과 일치) |
| [debate_bot/engine.py](debate_bot/engine.py) | 토론 진행, 프롬프트 구성, 완충 표현 점검 |
| [debate_bot/llm.py](debate_bot/llm.py) | OpenAI API 호출과 출처 수집 |
| [app.py](app.py) | Streamlit 화면 |

규칙을 바꾸려면 `docs/DEBATE_RULES.md`를 수정한다. 단계 구성을 바꿀 때는 `debate_format.py`도 함께 고친다.
