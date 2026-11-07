"""토론 진행 엔진. 규칙 문서를 시스템 지시문으로 삼아 단계별로 발언을 생성한다."""

import functools
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from . import llm
from .debate_format import STEPS, Step, format_table, opposite

RULES_PATH = Path(__file__).resolve().parent.parent / "docs" / "DEBATE_RULES.md"

# 규칙 제5장 3항에 열거된 완충 표현. 토론 단계 발언에서 발견되면 다시 쓰게 한다.
CUSHION_PATTERNS = [
    r"좋은 지적",
    r"훌륭한 (주장|지적|질문)",
    r"일리가 있",
    r"공감합니다",
    r"말씀하신 (대로|것처럼)",
    r"것 같습니다",
    r"것 같아요",
    r"조심스럽게",
    r"혹시",
    r"어떻게 보면",
    r"죄송하지만",
    r"실례지만",
]


def load_rules() -> str:
    return RULES_PATH.read_text(encoding="utf-8")


def find_cushions(text: str) -> list[str]:
    return [m.group(0) for p in CUSHION_PATTERNS for m in re.finditer(p, text)]


class BusyError(RuntimeError):
    """이전 API 요청이 아직 처리 중이다."""


def single_flight(method):
    """한 토론에서 API를 쓰는 작업이 동시에 두 개 실행되지 않게 한다. 중복 요청을 막기 위함."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self._lock.acquire(blocking=False):
            raise BusyError("이전 요청을 처리하고 있습니다.")
        try:
            return method(self, *args, **kwargs)
        finally:
            self._lock.release()
    return wrapper


@dataclass
class Turn:
    step: Step
    by_user: bool
    text: str
    sources: list[llm.Source] = field(default_factory=list)
    kind: str = "turn"


@dataclass
class ResearchNote:
    query: str
    text: str
    sources: list[llm.Source] = field(default_factory=list)
    kind: str = "research"


class Debate:
    def __init__(self, topic: str, user_side: str):
        self.topic = topic
        self.user_side = user_side
        self.bot_side = opposite(user_side)
        self.step_index = 0
        self.events: list[Turn | ResearchNote] = []
        self.review: llm.Reply | None = None
        self.rules = load_rules()
        self._lock = threading.Lock()

    # ---- 상태 ----

    @property
    def current_step(self) -> Step | None:
        return STEPS[self.step_index] if self.step_index < len(STEPS) else None

    @property
    def is_user_turn(self) -> bool:
        step = self.current_step
        return step is not None and step.side == self.user_side

    @property
    def debate_over(self) -> bool:
        return self.current_step is None

    @property
    def turns(self) -> list[Turn]:
        return [e for e in self.events if isinstance(e, Turn)]

    @property
    def research_notes(self) -> list[ResearchNote]:
        return [e for e in self.events if isinstance(e, ResearchNote)]

    # ---- 진행 ----

    def submit_user(self, text: str) -> Turn:
        if not self.is_user_turn:
            raise RuntimeError("지금은 사용자의 차례가 아닙니다.")
        turn = Turn(self.current_step, by_user=True, text=text)
        self.events.append(turn)
        self.step_index += 1
        return turn

    @single_flight
    def advance_bot(self) -> list[Turn]:
        """사용자 차례가 오거나 토론 단계가 끝날 때까지 챗봇 발언을 생성한다."""
        produced = []
        while self.current_step is not None and not self.is_user_turn:
            turn = self._bot_speech(self.current_step)
            self.events.append(turn)
            self.step_index += 1
            produced.append(turn)
        return produced

    @single_flight
    def request_research(self, query: str) -> ResearchNote:
        step = self.current_step
        task = (
            "현재 모드: **자료 조사 모드** (규칙 제8장).\n"
            f"사용자는 {self.user_side}측이며, 다음 사용자 발언 단계는 '{step.name if step else '없음'}'이다.\n"
            "웹 검색으로 사용자가 요청한 자료를 찾아 제8장 3항의 형식으로 정리하라. "
            "사용자 입장에 불리한 사실도 숨기지 말고, 각 자료의 한계와 예상 반박을 반드시 적어라."
        )
        reply = llm.generate(
            self._instructions(task),
            self._transcript_messages() + [{"role": "user", "content": f"[자료 요청]\n{query}"}],
            label="자료 요청",
        )
        note = ResearchNote(query, reply.text, reply.sources)
        self.events.append(note)
        return note

    @single_flight
    def run_review(self) -> llm.Reply:
        if not self.debate_over:
            raise RuntimeError("토론 단계가 아직 끝나지 않았습니다.")
        if self.review is not None:
            return self.review
        task = (
            "현재 모드: **정리 모드** (규칙 제9장). 당신은 이제 토론자가 아니라 중립적 진행자다.\n"
            "승패를 판정하지 말고, 제9장의 네 항목을 순서대로 작성하라. "
            f"챗봇({self.bot_side}측)의 근거도 사용자({self.user_side}측)의 근거와 같은 기준으로 평가하고 "
            "약점을 빠짐없이 지적하라(제7장)."
        )
        messages = self._transcript_messages()
        if self.research_notes:
            notes = "\n\n".join(f"- 요청: {n.query}\n{n.text}" for n in self.research_notes)
            messages.append({
                "role": "developer",
                "content": f"[참고: 토론 중 사용자가 요청해 받은 자료]\n{notes}\n\n"
                           "사용자가 이 자료를 실제 발언에서 어떻게 활용했는지(또는 하지 않았는지)도 평가하라.",
            })
        messages.append({"role": "developer", "content": "토론 정리를 시작하라."})
        self.review = llm.generate(self._instructions(task), messages, label="토론 정리")
        return self.review

    # ---- 프롬프트 구성 ----

    def _instructions(self, task: str) -> str:
        return (
            f"{self.rules}\n\n---\n\n"
            "# 이번 토론 정보\n"
            f"- 주제: {self.topic}\n"
            f"- 사용자: {self.user_side}측\n"
            f"- 챗봇: {self.bot_side}측 (역할로 배정된 입장)\n\n"
            f"## 진행 순서\n{format_table()}\n\n"
            f"# 지금 할 일\n{task}"
        )

    def _transcript_messages(self) -> list[dict]:
        messages = []
        for t in self.turns:
            who = "사용자" if t.by_user else "챗봇"
            messages.append({
                "role": "user" if t.by_user else "assistant",
                "content": f"[{t.step.name} | {t.step.side}측 · {who}]\n{t.text}",
            })
        return messages

    def _bot_speech(self, step: Step) -> Turn:
        number = STEPS.index(step) + 1
        task = (
            f"현재 모드: **토론자 모드**. 당신은 {self.bot_side}측 토론자다.\n"
            f"지금은 {number}단계 '{step.name}'이다. {step.guide} 분량은 {step.length}.\n"
            f"- 첫 줄에 `[{step.name} | {step.side}]`를 표기한다.\n"
            "- 직전 사용자 발언이 해당 단계의 범위를 벗어났다면 첫머리에서 한 문장으로 지적한다(제2장).\n"
            "- 상대 주장에 동조하지 말고 가장 강한 반론·반례를 제시한다(제4장).\n"
            "- 완충 표현·쿠션어 없이 단호하게 쓴다(제5장).\n"
            "- 법령·통계·기사는 웹 검색으로 확인하고 근거 등급과 출처를 표기한다(제6장). 등급은 "
            "[법령] [공식통계] [학술] [언론] [주장] [불확실] 중 하나만 쓰고 새 등급을 만들지 않는다.\n"
            "- 발언 전에 제7장 3항의 자체 점검을 수행하되, 점검 과정은 출력하지 않는다."
        )
        messages = self._transcript_messages() + [{"role": "developer", "content": f"'{step.name}' 발언을 하라."}]
        reply = llm.generate(self._instructions(task), messages, label=step.name)
        text = self._remove_cushions(reply.text)
        return Turn(step, by_user=False, text=text, sources=reply.sources)

    def _remove_cushions(self, text: str) -> str:
        found = find_cushions(text)
        if not found:
            return text
        rewrite = llm.generate(
            "너는 토론 발언 교정자다. 주어진 발언에서 지적된 완충 표현·쿠션어를 없애고 단호하고 직설적인 "
            "문장으로 고쳐 써라. 주장, 근거, 근거 등급 표기([법령], [불확실] 등), 출처, 단계 표기는 "
            "그대로 유지하고 내용을 추가하거나 빼지 마라. 고친 발언만 출력하라.",
            [{"role": "user", "content": f"지적된 표현: {', '.join(sorted(set(found)))}\n\n발언:\n{text}"}],
            web_search=False,
            label="완충 표현 재작성",
        )
        return rewrite.text

    # ---- 내보내기 ----

    def to_markdown(self) -> str:
        out = [f"# 토론 기록: {self.topic}", "", f"- 사용자: {self.user_side}측", f"- 챗봇: {self.bot_side}측", ""]
        for e in self.events:
            if isinstance(e, Turn):
                who = "사용자" if e.by_user else "챗봇"
                out += [f"## {e.step.name} ({e.step.side}측 · {who})", "", e.text, ""]
            else:
                out += [f"## 자료 요청: {e.query}", "", e.text, ""]
            out += [f"- [{s.title}]({s.url})" for s in e.sources] + ([""] if e.sources else [])
        if self.review:
            out += ["## 토론 정리", "", self.review.text, ""]
            out += [f"- [{s.title}]({s.url})" for s in self.review.sources]
        return "\n".join(out)
