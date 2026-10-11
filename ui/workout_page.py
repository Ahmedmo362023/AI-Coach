from datetime import date

import pandas as pd
import streamlit as st

from utils import db, llm, workouts as wk

COLUMNS = ["exercise", "muscle_group", "set_number", "reps", "weight_kg", "rpe"]
GROUPS = ["chest", "back", "shoulders", "biceps", "triceps", "legs", "glutes", "core", "cardio", "other"]

PLACEHOLDER = (
    "مثال: لعبت ضهر النهاردة. سحب عالي 3 مجاميع 15 عدة، الأولى 40 كيلو والتانية 45 والتالتة 50. "
    "وبعدين سحب أرضي 3 مجاميع 12 عدة بوزن 50."
)


def _log_tab(user) -> None:
    client = db.get_client()
    performed_on = st.date_input("Date", value=date.today(), max_value=date.today())
    text = st.text_area("What did you train?", height=150, placeholder=PLACEHOLDER)

    if st.button("Analyze with AI", disabled=not text.strip()):
        with st.spinner("Reading your workout..."):
            try:
                parsed = llm.parse_workout(text)
                st.session_state["wk_parsed"] = {
                    "title": parsed.get("title"),
                    "notes": parsed.get("notes"),
                    "warnings": parsed.get("warnings") or [],
                    "rows": wk.normalize(parsed),
                    "raw": text,
                }
            except Exception as e:  # noqa: BLE001
                st.session_state.pop("wk_parsed", None)
                st.error(f"Couldn't analyze the workout: {e}")

    p = st.session_state.get("wk_parsed")
    if not p:
        return

    st.markdown("#### Review before saving")
    for w in p["warnings"]:
        st.warning(w)
    if not p["rows"]:
        st.info("No valid sets found. Add rows below or rewrite the text with exercise names and reps.")

    df = pd.DataFrame(p["rows"], columns=COLUMNS)
    edited = st.data_editor(
        df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "exercise": st.column_config.TextColumn("Exercise", required=True),
            "muscle_group": st.column_config.SelectboxColumn("Muscle", options=GROUPS),
            "set_number": st.column_config.NumberColumn("Set", disabled=True),
            "reps": st.column_config.NumberColumn("Reps", min_value=1, max_value=200, step=1),
            "weight_kg": st.column_config.NumberColumn("Weight (kg)", min_value=0, step=0.5),
            "rpe": st.column_config.NumberColumn("RPE", min_value=1, max_value=10, step=0.5),
        },
        key="wk_editor",
    )
    title = st.text_input("Title", value=p["title"] or "")
    notes = st.text_area("Notes", value=p["notes"] or "", height=70)

    rows = wk.normalize(edited.to_dict("records"))
    c1, c2 = st.columns([1, 1])
    c1.metric("Valid sets", len(rows))
    c2.metric("Total volume (kg)", f"{wk.volume(rows):,.0f}")

    if st.button("Save workout", type="primary", disabled=not rows):
        try:
            wk.save_workout(client, user.id, performed_on, title, p["raw"], notes, rows)
        except Exception as e:  # noqa: BLE001
            st.error(f"Couldn't save: {e}")
        else:
            st.session_state.pop("wk_parsed", None)
            st.toast("Workout saved 💪")
            st.rerun()


def _history_tab() -> None:
    client = db.get_client()
    try:
        history = wk.fetch_recent(client)
    except Exception as e:  # noqa: BLE001
        st.error(f"Couldn't load history: {e}")
        return
    if not history:
        st.info("No workouts yet. Log your first one in the other tab.")
        return

    for w in history:
        label = f"{w['performed_on']} · {w.get('title') or 'Workout'} · {len(w['sets'])} sets"
        with st.expander(label):
            if w["sets"]:
                df = pd.DataFrame(w["sets"])[["exercise", "set_number", "reps", "weight_kg", "rpe"]]
                st.dataframe(df, hide_index=True, width="stretch")
                st.caption(f"Volume: {wk.volume(w['sets']):,.0f} kg")
            if w.get("notes"):
                st.caption(f"Notes: {w['notes']}")
            if st.button("Delete", key=f"del_{w['id']}"):
                wk.delete_workout(client, w["id"])
                st.rerun()


def render(user) -> None:
    tab_log, tab_hist = st.tabs(["Log workout", "History"])
    with tab_log:
        _log_tab(user)
    with tab_hist:
        _history_tab()
