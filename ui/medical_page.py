import streamlit as st

from utils import db, llm, rag

GOALS = {
    "Fat loss": "fat_loss", "Muscle gain": "muscle_gain",
    "Strength": "strength", "General fitness": "general_fitness",
}
EQUIPMENT = ["Full gym", "Dumbbells at home", "Bodyweight only"]
LANGUAGES = {"Egyptian Arabic": "Egyptian Arabic (colloquial, exercise names in English)", "English": "English"}

DISCLAIMER = "Not medical advice. Plans adapt to your report but never replace a doctor."


def _extract_cb() -> None:
    f = st.session_state.get("mr_file")
    st.session_state.pop("mr_error", None)
    if not f:
        return
    try:
        text = rag.extract_text(f.name, f.getvalue())
    except ValueError as e:
        st.session_state["mr_error"] = str(e)
        return
    st.session_state["mr_text"] = text
    if not st.session_state.get("mr_title"):
        st.session_state["mr_title"] = f.name.rsplit(".", 1)[0]
    st.session_state["mr_notice"] = (
        "Text extracted. Check it below: Arabic PDFs sometimes come out garbled. "
        "If so, paste the text instead."
    )


def _upload_tab(user) -> None:
    client = db.get_client()
    st.caption("Upload a PDF/TXT or paste the text of your report (radiology, blood tests, doctor notes).")
    st.file_uploader("Report file", type=["pdf", "txt"], key="mr_file")
    st.button("Extract text from file", on_click=_extract_cb, disabled=not st.session_state.get("mr_file"))
    if err := st.session_state.pop("mr_error", None):
        st.error(err)
    if note := st.session_state.pop("mr_notice", None):
        st.info(note)

    st.text_input("Title", placeholder="e.g. Knee MRI, Oct 2026", key="mr_title")
    st.text_area("Report text", height=260, key="mr_text",
                 help="Review and edit before saving. Remove your name, ID and phone number if you like.")
    consent = st.checkbox(
        "I understand this text is sent to Google's Gemini API to be indexed and used by the coach, "
        "and I can delete it any time.",
        key="mr_consent",
    )
    text = st.session_state.get("mr_text", "")
    if st.button("Save and index report", type="primary", key="mr_save",
                 disabled=not (consent and len(text.strip()) >= 30)):
        with st.spinner("Splitting and indexing..."):
            try:
                _, n = rag.index_report(client, user.id, st.session_state.get("mr_title", ""),
                                        text, llm.embed_texts)
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                if "report_chunks" in msg or "match_report_chunks" in msg:
                    st.error("The database is missing the report tables. Run "
                             "db/migrations/003_report_rag.sql in the Supabase SQL Editor, then try again.")
                else:
                    st.error(f"Couldn't index the report: {e}")
                return
        for k in ("mr_text", "mr_title", "mr_consent", "mr_file"):
            st.session_state.pop(k, None)
        st.toast(f"Report saved ({n} chunks) 📄")
        st.rerun()

    st.markdown("#### My reports")
    try:
        reports = rag.list_reports(client)
    except Exception as e:  # noqa: BLE001
        st.error(f"Couldn't load your reports: {e}")
        return
    if not reports:
        st.info("No reports yet.")
    for r in reports:
        c = st.columns([5, 2, 1.4])
        c[0].markdown(f"**{r['title']}**")
        c[1].caption(f"{str(r['created_at'])[:10]} · {r['chars']:,} chars")
        with c[2].popover("Delete"):
            st.write("Delete this report and its index?")
            if st.button("Yes, delete", key=f"delr_{r['id']}"):
                rag.delete_report(client, r["id"])
                st.rerun()


def _report_choice(client, key: str):
    """Returns (ok, report_id or None). Lets the user scope to one report."""
    try:
        reports = rag.list_reports(client)
    except Exception as e:  # noqa: BLE001
        st.error(f"Couldn't load your reports: {e}")
        return False, None
    if not reports:
        st.info("Add a report in the first tab.")
        return False, None
    options = {"All my reports": None, **{r["title"] + " · " + str(r["created_at"])[:10]: r["id"] for r in reports}}
    label = st.selectbox("Use", list(options), key=key)
    return True, options[label]


def _sources(chunks: list[dict]) -> None:
    with st.expander(f"Report excerpts used ({len(chunks)})"):
        for i, c in enumerate(chunks, 1):
            st.markdown(f"**[{i}]** similarity {c['similarity']:.2f}")
            st.text(c["content"])


def _ask_tab() -> None:
    client = db.get_client()
    ok, report_id = _report_choice(client, "mr_ask_scope")
    if not ok:
        return
    q = st.text_input("Ask about your report", placeholder="مثلا: التقرير بيقول إيه عن الركبة؟", key="mr_q")
    if st.button("Ask", disabled=not q.strip(), key="mr_ask"):
        with st.spinner("Reading your report..."):
            try:
                chunks = rag.search(client, q, llm.embed_texts, k=5, report_id=report_id)
                answer = llm.answer_from_report(q, chunks) if chunks else "Nothing found in your reports."
                st.session_state["mr_answer"] = {"text": answer, "chunks": chunks}
            except Exception as e:  # noqa: BLE001
                st.session_state.pop("mr_answer", None)
                st.error(f"Couldn't answer: {e}")
    a = st.session_state.get("mr_answer")
    if a:
        st.markdown(a["text"])
        if a["chunks"]:
            _sources(a["chunks"])
        st.caption(DISCLAIMER)


def _plan_tab() -> None:
    client = db.get_client()
    ok, report_id = _report_choice(client, "mr_plan_scope")
    if not ok:
        return
    c1, c2, c3 = st.columns(3)
    goal = c1.selectbox("Goal", list(GOALS), key="mr_goal")
    experience = c2.selectbox("Experience", ["beginner", "intermediate", "advanced"], key="mr_exp")
    days = c3.slider("Days per week", 2, 6, 4, key="mr_days")
    c4, c5 = st.columns(2)
    equipment = c4.selectbox("Equipment", EQUIPMENT, key="mr_equip")
    language = c5.selectbox("Plan language", list(LANGUAGES), key="mr_lang")
    notes = st.text_input("Anything else? (optional)", key="mr_notes")

    if st.button("Build my plan", type="primary", key="mr_plan_btn"):
        with st.spinner("Reading your report and building the plan..."):
            try:
                chunks = rag.search(client, rag.TRAINING_QUERIES, llm.embed_texts, k=3,
                                    report_id=report_id, max_total=8)
                plan = llm.build_plan(
                    {"goal": goal, "experience": experience, "days": days, "equipment": equipment,
                     "notes": notes, "language": LANGUAGES[language]},
                    chunks,
                )
                st.session_state["mr_plan"] = {"text": plan, "chunks": chunks}
            except Exception as e:  # noqa: BLE001
                st.session_state.pop("mr_plan", None)
                st.error(f"Couldn't build the plan: {e}")
    p = st.session_state.get("mr_plan")
    if p:
        st.markdown(p["text"])
        _sources(p["chunks"])
        st.caption(DISCLAIMER)


def render(user) -> None:
    tab_up, tab_ask, tab_plan = st.tabs(["Reports", "Ask your report", "Adjust my plan"])
    with tab_up:
        _upload_tab(user)
    with tab_ask:
        _ask_tab()
    with tab_plan:
        _plan_tab()
