from datetime import date

import pandas as pd
import streamlit as st

from utils import db, llm, meals as ml

COLUMNS = ["meal_type", "name", "calories", "protein_g", "carbs_g", "fat_g"]

PLACEHOLDER = (
    "مثال: فطار 3 بيضات مسلوقة وعيش بلدي وكوب شاي بلبن. "
    "غدا نص كيلو فراخ مشوية مع كوباية رز وسلطة."
)


def _show_totals(t: dict) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Calories", f"{t['calories']:,.0f} kcal")
    c2.metric("Protein", f"{t['protein_g']:,.0f} g")
    c3.metric("Carbs", f"{t['carbs_g']:,.0f} g")
    c4.metric("Fat", f"{t['fat_g']:,.0f} g")


def _log_tab(user) -> None:
    client = db.get_client()
    eaten_on = st.date_input("Date", value=date.today(), max_value=date.today(), key="ml_date")
    text = st.text_area("What did you eat?", height=140, placeholder=PLACEHOLDER, key="ml_text")

    if st.button("Analyze with AI", disabled=not text.strip(), key="ml_analyze"):
        with st.spinner("Estimating nutrition..."):
            try:
                parsed = llm.parse_meals(text)
                st.session_state["ml_parsed"] = {
                    "warnings": parsed.get("warnings") or [],
                    "rows": ml.normalize(parsed),
                }
            except Exception as e:  # noqa: BLE001
                st.session_state.pop("ml_parsed", None)
                st.error(f"Couldn't analyze the food log: {e}")

    p = st.session_state.get("ml_parsed")
    if not p:
        return

    st.markdown("#### Review before saving")
    st.caption("Values are AI estimates. Edit anything that looks off.")
    for w in p["warnings"]:
        st.warning(w)
    if not p["rows"]:
        st.info("No food items found. Add rows below or rewrite with food names and quantities.")

    df = pd.DataFrame(p["rows"], columns=COLUMNS)
    edited = st.data_editor(
        df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "meal_type": st.column_config.SelectboxColumn("Meal", options=ml.MEAL_TYPES),
            "name": st.column_config.TextColumn("Item", required=True),
            "calories": st.column_config.NumberColumn("kcal", min_value=0, step=5),
            "protein_g": st.column_config.NumberColumn("Protein (g)", min_value=0, step=1),
            "carbs_g": st.column_config.NumberColumn("Carbs (g)", min_value=0, step=1),
            "fat_g": st.column_config.NumberColumn("Fat (g)", min_value=0, step=1),
        },
        key="ml_editor",
    )

    rows = ml.normalize(edited.to_dict("records"))
    bad = [r["name"] for r in rows if ml.inconsistent(r)]
    if bad:
        st.caption("⚠ Calories don't match the macros for: " + ", ".join(bad))
    _show_totals(ml.totals(rows))

    if st.button("Save to my log", type="primary", disabled=not rows, key="ml_save"):
        try:
            ml.save_meals(client, user.id, eaten_on, rows)
        except Exception as e:  # noqa: BLE001
            if "meal_type" in str(e):
                st.error(
                    "The database is missing the meal_type column. Run "
                    "db/migrations/002_meals_meal_type.sql in the Supabase SQL Editor, then try again."
                )
            else:
                st.error(f"Couldn't save: {e}")
        else:
            st.session_state.pop("ml_parsed", None)
            st.toast("Meals saved 🍽️")
            st.rerun()


def _history_tab() -> None:
    client = db.get_client()
    try:
        days = ml.fetch_days(client)
    except Exception as e:  # noqa: BLE001
        st.error(f"Couldn't load your log: {e}")
        return
    if not days:
        st.info("Nothing logged yet. Add your first meal in the other tab.")
        return

    for i, d in enumerate(days):
        t = d["totals"]
        label = f"{d['day']} · {t['calories']:,.0f} kcal · P {t['protein_g']:,.0f} g"
        with st.expander(label, expanded=(i == 0)):
            for it in d["items"]:
                c = st.columns([5, 1.3, 1.3, 1.3, 1.3, 0.8])
                c[0].markdown(f"**{it.get('meal_type') or 'other'}** · {it['name']}")
                c[1].caption(f"{it.get('calories') or 0:,.0f} kcal")
                c[2].caption(f"P {it.get('protein_g') or 0:,.0f}")
                c[3].caption(f"C {it.get('carbs_g') or 0:,.0f}")
                c[4].caption(f"F {it.get('fat_g') or 0:,.0f}")
                if c[5].button("✕", key=f"delm_{it['id']}", help="Delete this item"):
                    ml.delete_meal(client, it["id"])
                    st.rerun()
            st.caption(
                f"Day total: {t['calories']:,.0f} kcal · protein {t['protein_g']:,.0f} g · "
                f"carbs {t['carbs_g']:,.0f} g · fat {t['fat_g']:,.0f} g"
            )


def render(user) -> None:
    tab_log, tab_hist = st.tabs(["Log food", "Daily log"])
    with tab_log:
        _log_tab(user)
    with tab_hist:
        _history_tab()
