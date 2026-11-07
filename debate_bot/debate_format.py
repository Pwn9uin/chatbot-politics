"""토론 형식 정의. docs/DEBATE_RULES.md 제2장의 표와 일치해야 한다."""

from dataclasses import dataclass

PRO = "찬성"
CON = "반대"


def opposite(side: str) -> str:
    return CON if side == PRO else PRO


@dataclass(frozen=True)
class Step:
    name: str
    side: str
    guide: str  # 이 단계에서 발언자가 해야 하는 일
    length: str


STEPS: list[Step] = [
    Step("찬성 입론", PRO, "핵심 주장 2~3개와 각 주장의 근거를 제시한다.", "400~700자"),
    Step("반대 입론", CON, "핵심 주장 2~3개와 각 주장의 근거를 제시한다. 찬성 입론에 대한 반박은 하지 않는다.", "400~700자"),
    Step("교차조사 — 반대측 질문", CON, "찬성 입론의 전제·근거를 겨냥한 질문을 최대 3개 던진다. 질문만 하고 주장은 하지 않는다.", "200~500자"),
    Step("교차조사 — 찬성측 답변", PRO, "직전 단계의 질문에 하나씩 답한다. 새로운 주장을 추가하지 않는다.", "200~500자"),
    Step("교차조사 — 찬성측 질문", PRO, "반대 입론의 전제·근거를 겨냥한 질문을 최대 3개 던진다. 질문만 하고 주장은 하지 않는다.", "200~500자"),
    Step("교차조사 — 반대측 답변", CON, "직전 단계의 질문에 하나씩 답한다. 새로운 주장을 추가하지 않는다.", "200~500자"),
    Step("반대 반론", CON, "찬성측 주장과 교차조사 답변의 허점을 반박한다.", "400~700자"),
    Step("찬성 반론", PRO, "반대측 주장과 교차조사 답변의 허점을 반박한다.", "400~700자"),
    Step("반대 최종변론", CON, "새로운 근거 없이 쟁점을 정리하고 자기 입장이 우세한 이유를 제시한다.", "200~500자"),
    Step("찬성 최종변론", PRO, "새로운 근거 없이 쟁점을 정리하고 자기 입장이 우세한 이유를 제시한다.", "200~500자"),
]


def format_table() -> str:
    lines = ["| 순서 | 단계 | 발언자 |", "|---|---|---|"]
    for i, step in enumerate(STEPS, 1):
        lines.append(f"| {i} | {step.name} | {step.side} |")
    lines.append(f"| {len(STEPS) + 1} | 토론 정리 | 진행자 |")
    return "\n".join(lines)
