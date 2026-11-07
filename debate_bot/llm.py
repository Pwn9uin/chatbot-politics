"""OpenAI Responses API 호출. 웹 검색으로 법령·기사 등 근거를 찾고 출처를 함께 돌려준다."""

import os
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
WEB_SEARCH_TOOL = {
    "type": "web_search",
    "user_location": {"type": "approximate", "country": "KR"},
}

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        # OPENAI_API_KEY 환경 변수 사용. 시간 초과 후 재시도하면 같은 요청이 이중 과금될 수 있어
        # 재시도는 1회로 제한한다.
        _client = OpenAI(timeout=300, max_retries=1)
    return _client


@dataclass
class Source:
    title: str
    url: str


@dataclass
class Reply:
    text: str
    sources: list[Source] = field(default_factory=list)


def generate(instructions: str, messages: list[dict], web_search: bool = True, label: str = "") -> Reply:
    print(f"[OpenAI] 요청 시작: {label} (모델 {MODEL}, 웹 검색 {'사용' if web_search else '안 함'})", flush=True)
    started = time.monotonic()
    response = client().responses.create(
        model=MODEL,
        instructions=instructions,
        input=messages,
        tools=[WEB_SEARCH_TOOL] if web_search else [],
    )
    searches = sum(1 for item in response.output if item.type == "web_search_call")
    usage = response.usage
    print(
        f"[OpenAI] 완료: {label} {time.monotonic() - started:.1f}초, 웹 검색 {searches}회, "
        f"토큰 입력 {usage.input_tokens if usage else '?'} / 출력 {usage.output_tokens if usage else '?'}",
        flush=True,
    )
    return Reply(text=response.output_text.strip(), sources=_collect_sources(response))


def _collect_sources(response) -> list[Source]:
    seen: dict[str, Source] = {}
    for item in response.output:
        if item.type != "message":
            continue
        for part in item.content:
            for ann in getattr(part, "annotations", None) or []:
                if ann.type == "url_citation" and ann.url not in seen:
                    seen[ann.url] = Source(title=ann.title or ann.url, url=ann.url)
    return list(seen.values())
