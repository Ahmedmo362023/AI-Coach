from datetime import date

import plotly.graph_objects as go
import streamlit as st

from utils import analytics as an, db
from utils.theme import RED

GOALS = {"Fat loss": "fat_loss", "Muscle gain": "muscle_gain",
         "Strength": "strength", "General fitness": "general_fitness"}
LEVELS = ["beginner", "intermediate", "advanced"]


def _profile_form(client, user, profile: dict) -> None:
    with st.expander("My profile", expanded=not profile.get("goal")):
        goal_labels = list(GOALS)
        cur_goal = next((k for k, v in GOALS.items() if v == profile.get("goal")), goal_labels[0])
        with st.form("profile_form"):
            c1, c2, c3 = st.columns(3)
            goal = c1.selectbox("Goal", goal_labels, index=goal_labels.index(cur_goal))
            level = c2.selectbox("Experience", LEVELS,
                                 index=LEVELS.index(profile["experience"]) if profile.get("experience") in LEVELS else 0)
            days = c3.slider("Sessions per week", 1, 7, int(profile.get("days_per_week") or 4))
            c4, c5, c6 = st.columns(3)
            age = c4.number_input("Age", 12, 100, int(profile.get("age") or 25))
            height = c5.number_input("Height (cm)", 100, 250, int(float(profile.get("height_cm") or 170)))
            weight = c6.number_input("Weight (kg)", 25.0, 400.0, float(profile.get("weight_kg") or 70.0), step=0.5)
            if st.form_submit_button("Save profile"):
                try:
                    an.save_profile(client, user.id, goal=GOALS[goal], experience=level, days_per_week=days,
                                    age=int(age), height_cm=float(height), weight_kg=float(weight))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Couldn't save: {e}")
                else:
                    st.toast("Profile saved")
                    st.rerun()


def _weight_form(client, user) -> None:
    with st.form("weight_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 1, 1])
        d = c1.date_input("Date", value=date.today(), max_value=date.today())
        w = c2.number_input("Body weight (kg)", 25.0, 400.0, 70.0, step=0.1)
        c3.write("")
        if c3.form_submit_button("Log weight"):
            try:
                an.add_weight(client, user.id, d, float(w))
            except Exception as e:  # noqa: BLE001
                st.error(f"Couldn't save: {e}")
            else:
                st.toast("Weight logged")
                st.rerun()


def _style(fig: go.Figure, title: str, height: int = 280) -> go.Figure:
    """Shared black/red look for every chart."""
    fig.update_layout(
        title=dict(text=title, font=dict(color="#F5F5F5", size=16), x=0.0),
        height=height,
        margin=dict(l=10, r=10, t=48, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#BDBDBD"),
        hoverlabel=dict(bgcolor="#1C1C1C", bordercolor=RED, font=dict(color="#F5F5F5")),
        xaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="#2A2A2A", showgrid=False),
        yaxis=dict(gridcolor="#222222", zeroline=False),
    )
    return fig


def _bar(rows, x, y, title):
    fig = go.Figure(go.Bar(
        x=[r[x] for r in rows], y=[r[y] for r in rows],
        marker=dict(color=RED, line=dict(width=0)),
    ))
    fig.update_traces(marker_cornerradius=6)
    return _style(fig, title)


def _weight_line(pts):
    fig = go.Figure(go.Scatter(
        x=[p[0] for p in pts], y=[p[1] for p in pts],
        mode="lines+markers",
        line=dict(color=RED, width=3, shape="spline", smoothing=0.6),
        marker=dict(size=8, color=RED, line=dict(color="#0A0A0A", width=2)),
    ))
    return _style(fig, "Body weight (kg)", height=260)


def render(user) -> None:
    client = db.get_client()
    try:
        profile = an.get_profile(client, user.id)
        data = an.fetch_data(client)
    except Exception as e:  # noqa: BLE001
        st.error(f"Couldn't load your data: {e}")
        return

    _profile_form(client, user, profile)
    m = an.compute_metrics(data["workouts"], data["sets"], data["meals"], data["body"], profile)

    st.markdown("#### Last 7 days")
    t, n, b = m["training"], m["nutrition"], m["body"]
    c = st.columns(4)
    plan = m["profile"]["planned_sessions_per_week"]
    c[0].metric("Sessions", f"{t['sessions']}" + (f" / {plan}" if plan else ""))
    c[1].metric("Volume", f"{t['volume_kg']:,.0f} kg", None if t["volume_change_pct"] is None else f"{t['volume_change_pct']:+.0f}%")
    c[2].metric("Avg calories", "—" if n["avg_calories"] is None else f"{n['avg_calories']:,.0f}",
                help=f"Average over {n['days_logged']} logged day(s)")
    c[3].metric("Weight", "—" if b["latest_weight_kg"] is None else f"{b['latest_weight_kg']:.1f} kg",
                None if b["change_vs_previous_period_kg"] is None else f"{b['change_vs_previous_period_kg']:+.1f} kg")
    for f in m["flags"]:
        st.warning(f)
    for pr in t["personal_records"]:
        st.success(f"New PR: {pr['exercise']} ≈ {pr['e1rm_kg']} kg (est. 1RM), was {pr['previous_kg']} kg")

    wk = an.weekly_volume_series(data["sets"])
    nut = an.daily_nutrition_series(data["meals"])
    has_wk = any(r["volume_kg"] for r in wk)
    has_nut = any(r["calories"] for r in nut)

    if has_wk or has_nut:
        st.markdown("#### Trends")
    if has_wk and has_nut:
        l, r = st.columns(2)
        l.plotly_chart(_bar(wk, "week_ending", "volume_kg", "Weekly training volume (kg)"), width="stretch")
        r.plotly_chart(_bar(nut, "day", "calories", "Daily calories (last 14 days)"), width="stretch")
    elif has_wk:
        st.plotly_chart(_bar(wk, "week_ending", "volume_kg", "Weekly training volume (kg)"), width="stretch")
    elif has_nut:
        st.plotly_chart(_bar(nut, "day", "calories", "Daily calories (last 14 days)"), width="stretch")
    else:
        st.info("Log a workout or a meal and your charts will show up here.")

    st.markdown("#### Log body weight")
    _weight_form(client, user)
    pts = sorted((x["measured_on"], x["weight_kg"]) for x in data["body"] if x.get("weight_kg"))
    if len(pts) >= 2:
        st.plotly_chart(_weight_line(pts), width="stretch")