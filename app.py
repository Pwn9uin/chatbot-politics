"""정치 토론 시뮬레이션 챗봇 — Streamlit UI.

실행: streamlit run app.py
"""

import streamlit as st

from debate_bot.debate_format import CON, PRO, STEPS
from debate_bot.engine import BusyError, Debate, ResearchNote, load_rules

st.set_page_config(page_title="정치 토론 시뮬레이터", page_icon="⚖️", layout="wide")


def show_sources(sources):
    if sources:
        with st.expander(f"출처 {len(sources)}건"):
            for s in sources:
                st.markdown(f"- [{s.title}]({s.url})")


def call_api(fn, *args):
    try:
        return fn(*args)
    except BusyError:
        st.info("이전 요청을 처리하고 있습니다. 잠시 후 다시 시도하세요.")
        st.stop()
    except Exception as e:
        # 실패를 기록해 두고 자동 재시도를 멈춘다. 다시 요청하려면 사용자가 버튼을 눌러야 한다.
        st.session_state["api_error"] = f"{type(e).__name__}: {e}"
        st.rerun()


debate: Debate | None = st.session_state.get("debate")

# ---- 사이드바: 규칙과 진행 상황 ----
with st.sidebar:
    st.header("토론 진행 순서")
    for i, step in enumerate(STEPS):
        if debate is None:
            mark = "▫️"
        elif i < debate.step_index:
            mark = "✅"
        elif i == debate.step_index:
            mark = "▶️"
        else:
            mark = "▫️"
        owner = "" if debate is None else (" (나)" if step.side == debate.user_side else " (챗봇)")
        st.markdown(f"{mark} {i + 1}. {step.name}{owner}")
    st.markdown(f"{'✅' if debate and debate.review else '▫️'} {len(STEPS) + 1}. 토론 정리")

    with st.expander("토론 규칙 전문"):
        st.markdown(load_rules())

    if debate and st.button("새 토론 시작", use_container_width=True):
        del st.session_state["debate"]
        st.session_state.pop("api_error", None)
        st.rerun()

st.title("⚖️ 정치 토론 시뮬레이터")

# ---- 토론 설정 ----
if debate is None:
    st.write("토론 주제와 내 입장을 정하면, 챗봇이 반대편 입장을 맡아 규칙에 따라 토론을 진행합니다.")
    with st.form("setup"):
        topic = st.text_input("토론 주제", placeholder="예: 국회의원 선거에 완전 비례대표제를 도입해야 한다")
        side = st.radio("내 입장", [PRO, CON], horizontal=True)
        if st.form_submit_button("토론 시작", type="primary") and topic.strip():
            st.session_state["debate"] = Debate(topic.strip(), side)
            st.rerun()
    st.stop()

st.subheader(f"주제: {debate.topic}")
st.caption(f"나: {debate.user_side}측 · 챗봇: {debate.bot_side}측")

# ---- 토론 기록 ----
for e in debate.events:
    if isinstance(e, ResearchNote):
        with st.chat_message("assistant", avatar="📚"):
            st.markdown(f"**자료 요청:** {e.query}")
            st.markdown(e.text)
            show_sources(e.sources)
    else:
        with st.chat_message("user" if e.by_user else "assistant"):
            st.caption(f"{e.step.name} · {e.step.side}측 ({'나' if e.by_user else '챗봇'})")
            st.markdown(e.text)
            show_sources(e.sources)

# ---- API 실패: 사용자가 확인하기 전까지 자동 요청을 하지 않는다 ----
if error := st.session_state.get("api_error"):
    st.error(f"OpenAI API 요청이 실패했습니다. 자동으로 다시 요청하지 않습니다.\n\n{error}")
    if st.button("다시 시도"):
        del st.session_state["api_error"]
        st.rerun()
    st.stop()

# ---- 챗봇 차례 ----
if not debate.debate_over and not debate.is_user_turn:
    with st.spinner(f"챗봇이 '{debate.current_step.name}' 발언을 준비하고 있습니다… (자료 검색 포함)"):
        call_api(debate.advance_bot)
    st.rerun()

# ---- 사용자 차례 ----
if debate.is_user_turn:
    step = debate.current_step
    st.info(f"**{STEPS.index(step) + 1}단계 · {step.name}** (내 차례)\n\n{step.guide} 권장 분량: {step.length}")

    with st.expander("📚 발언 전에 자료 요청하기"):
        with st.form("research", clear_on_submit=True):
            query = st.text_area("필요한 자료", placeholder="예: 비례대표제를 도입한 국가들의 정당 수 변화에 관한 연구")
            if st.form_submit_button("자료 찾기") and query.strip():
                with st.spinner("자료를 찾고 있습니다…"):
                    call_api(debate.request_research, query.strip())
                st.rerun()

    if speech := st.chat_input(f"{step.name} 발언을 입력하세요"):
        debate.submit_user(speech)
        st.rerun()

# ---- 토론 정리 ----
if debate.debate_over:
    if debate.review is None:
        with st.spinner("토론을 정리하고 근거별 피드백을 작성하고 있습니다…"):
            call_api(debate.run_review)
        st.rerun()
    with st.chat_message("assistant", avatar="🧑‍⚖️"):
        st.caption("토론 정리 · 진행자")
        st.markdown(debate.review.text)
        show_sources(debate.review.sources)
    st.download_button("토론 기록 내려받기 (.md)", debate.to_markdown(), file_name="debate.md")
