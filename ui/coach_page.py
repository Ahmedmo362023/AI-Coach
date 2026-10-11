import time

import streamlit as st

from utils import analytics as an, chat, db, llm, rag

LANGUAGES = {"Egyptian Arabic": "Egyptian Arabic (colloquial, exercise names in English)", "English": "English"}
DISCLAIMER = "Not medical advice. Plans adapt to your report but never replace a doctor."


def _generate(client, user, language: str) -> None:
    profile = an.get_profile(client, user.id)
    data = an.fetch_data(client)
    metrics = an.compute_metrics(data["workouts"], data["sets"], data["meals"], data["body"], profile)
    chunks: list[dict] = []
    try:  # the report is optional: no report or no embeddings must not block the coach
        if rag.list_reports(client):
            chunks = rag.search(client, rag.TRAINING_QUERIES, llm.embed_texts, k=2, max_total=6)
    except Exception:  # noqa: BLE001
        chunks = []
    text = llm.coach_report(metrics, chunks, LANGUAGES[language])
    an.save_report(client, user.id, metrics, text)
    st.session_state["mr_coach"] = {"text": text, "metrics": metrics, "chunks": chunks}


def _reports_tab(client, user) -> None:
    st.caption("Your numbers are computed in code. The coach only explains them.")
    c1, c2 = st.columns([1, 2])
    language = c1.selectbox("Report language", list(LANGUAGES), key="mr_coach_lang")
    if c2.button("Generate this week's report", type="primary", key="mr_coach_btn"):
        with st.spinner("Crunching your week..."):
            try:
                _generate(client, user, language)
            except Exception as e:  # noqa: BLE001
                st.session_state.pop("mr_coach", None)
                st.error(f"Couldn't build the report: {e}")

    r = st.session_state.get("mr_coach")
    if r:
        st.markdown(r["text"])
        for f in r["metrics"]["flags"]:
            st.caption(f"⚑ {f}")
        with st.expander("Numbers behind this report"):
            st.json(r["metrics"])
        if r["chunks"]:
            with st.expander(f"Report excerpts used ({len(r['chunks'])})"):
                for i, c in enumerate(r["chunks"], 1):
                    st.markdown(f"**[{i}]**")
                    st.text(c["content"])
        st.caption(DISCLAIMER)

    st.markdown("#### Past reports")
    try:
        past = an.list_reports(client)
    except Exception as e:  # noqa: BLE001
        st.error(f"Couldn't load past reports: {e}")
        return
    if not past:
        st.info("No reports yet.")
    for p in past:
        with st.expander(f"{p['period_start']} → {p['period_end']}"):
            st.markdown(p["report_text"])


# ---------- Chat ----------
CHAT_KEY, CHAT_STAMPS, CHAT_CTX = "ch_messages", "ch_stamps", "ch_ctx"
STARTERS = ["How was my week?", "What should I eat today?", "Am I progressing on my lifts?"]


def _answer(client, user, question: str, language: str) -> str:
    """Build the context in code (cached for the chat), fetch report excerpts only if relevant, ask the LLM."""
    ctx = st.session_state.get(CHAT_CTX)
    if ctx is None:
        profile = an.get_profile(client, user.id)
        data = an.fetch_data(client, days=120)
        ctx = chat.build_context(profile, data)
        st.session_state[CHAT_CTX] = ctx
    chunks: list[dict] = []
    if chat.wants_report(question):
        try:
            if rag.list_reports(client):
                chunks = rag.search(client, [question] + rag.TRAINING_QUERIES[:2], llm.embed_texts,
                                    k=2, max_total=5)
        except Exception:  # noqa: BLE001
            chunks = []
    history = chat.trim_history(st.session_state.get(CHAT_KEY, []))
    return llm.coach_chat(history, question, ctx, chunks, LANGUAGES[language])


def _chat_tab(client, user) -> None:
    msgs: list[dict] = st.session_state.setdefault(CHAT_KEY, [])
    c1, c2, c3 = st.columns([1, 1, 2])
    language = c1.selectbox("Chat language", list(LANGUAGES), key="ch_lang")
    if c2.button("New chat", key="ch_new"):
        for k in (CHAT_KEY, CHAT_CTX):
            st.session_state.pop(k, None)
        st.rerun()
    if c3.button("Refresh my data", key="ch_refresh", help="Reload your latest logs into the chat"):
        st.session_state.pop(CHAT_CTX, None)
        st.toast("Data will be reloaded on your next message")
    st.caption("Ask about your week, food, lifts or medical report. Answers use your real logged numbers.")

    for m in msgs:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    question = None
    if not msgs:
        cols = st.columns(len(STARTERS))
        for col, s in zip(cols, STARTERS):
            if col.button(s, key=f"ch_s_{s}"):
                question = s
    typed = st.chat_input("Ask your coach...", key="ch_input")
    question = chat.clean_question(typed or question or "")
    if question:
        if len(msgs) >= chat.MAX_MESSAGES:
            st.warning("This chat is long. Press New chat to start fresh.")
            return
        blocked, wait = chat.rate_limited(st.session_state.get(CHAT_STAMPS, []))
        if blocked:
            st.warning(f"Slow down a little: try again in about {wait} seconds.")
            return
        st.session_state[CHAT_STAMPS] = [*st.session_state.get(CHAT_STAMPS, []), time.time()][-50:]
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    reply = _answer(client, user, question, language)
                except Exception as e:  # noqa: BLE001
                    st.error(f"Couldn't get an answer: {e}")
                    return
            st.markdown(reply)
        msgs += [{"role": "user", "content": question}, {"role": "assistant", "content": reply}]
    st.caption(DISCLAIMER)


def render(user) -> None:
    client = db.get_client()
    t_chat, t_report = st.tabs(["Chat", "Weekly report"])
    with t_chat:
        _chat_tab(client, user)
    with t_report:
        _reports_tab(client, user)