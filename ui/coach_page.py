import streamlit as st

from utils import analytics as an, db, llm, rag

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


def render(user) -> None:
    client = db.get_client()
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
