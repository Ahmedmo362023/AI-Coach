from datetime import date
from html import escape

import plotly.graph_objects as go
import streamlit as st

from utils import analytics as an, db, progress as pg
from utils.theme import RED

GOALS = {"Fat loss": "fat_loss", "Muscle gain": "muscle_gain",
         "Strength": "strength", "General fitness": "general_fitness"}
LEVELS = ["beginner", "intermediate", "advanced"]
SEX = {"Not set": None, "Male": "male", "Female": "female"}
HISTORY_DAYS = 180  # how far back the dashboard looks (streaks, exercise history)


def _profile_form(client, user, profile: dict) -> None:
    with st.expander("My profile", expanded=not profile.get("goal")):
        goal_labels = list(GOALS)
        cur_goal = next((k for k, v in GOALS.items() if v == profile.get("goal")), goal_labels[0])
        sex_labels = list(SEX)
        cur_sex = next((k for k, v in SEX.items() if v == profile.get("sex")), "Not set")
        with st.form("profile_form"):
            c1, c2, c3 = st.columns(3)
            goal = c1.selectbox("Goal", goal_labels, index=goal_labels.index(cur_goal))
            level = c2.selectbox("Experience", LEVELS,
                                 index=LEVELS.index(profile["experience"]) if profile.get("experience") in LEVELS else 0)
            days = c3.slider("Sessions per week", 1, 7, int(profile.get("days_per_week") or 4))
            c4, c5, c6, c7 = st.columns(4)
            age = c4.number_input("Age", 12, 100, int(profile.get("age") or 25))
            height = c5.number_input("Height (cm)", 100, 250, int(float(profile.get("height_cm") or 170)))
            weight = c6.number_input("Weight (kg)", 25.0, 400.0, float(profile.get("weight_kg") or 70.0), step=0.5)
            sex = c7.selectbox("Sex", sex_labels, index=sex_labels.index(cur_sex),
                               help="Only used to make the daily calorie estimate more accurate.")
            if st.form_submit_button("Save profile"):
                fields = dict(goal=GOALS[goal], experience=level, days_per_week=days,
                              age=int(age), height_cm=float(height), weight_kg=float(weight))
                if "sex" in profile or SEX[sex]:  # older databases don't have the column yet
                    fields["sex"] = SEX[sex]
                try:
                    an.save_profile(client, user.id, **fields)
                except Exception as e:  # noqa: BLE001
                    if "sex" in str(e):
                        st.error("The database is missing the sex column. Run "
                                 "db/migrations/004_profile_sex.sql in the Supabase SQL Editor, then try again.")
                    else:
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


def _exercise_chart(hist: list[dict], name: str) -> go.Figure:
    x = [h["date"] for h in hist]
    marker = dict(size=8, color=RED, line=dict(color="#0A0A0A", width=2))
    fig = go.Figure()
    if any(h["top_weight"] for h in hist):
        fig.add_trace(go.Scatter(
            x=x, y=[h["top_weight"] for h in hist], name="Top set (kg)", mode="lines+markers",
            line=dict(color="#BDBDBD", width=2, dash="dot"), marker=dict(size=7, color="#BDBDBD")))
        fig.add_trace(go.Scatter(
            x=x, y=[h["e1rm"] for h in hist], name="Est. 1RM (kg)", mode="lines+markers",
            connectgaps=True, line=dict(color=RED, width=3), marker=marker))
    else:  # bodyweight exercise: show reps instead
        fig.add_trace(go.Scatter(
            x=x, y=[h["top_reps"] for h in hist], name="Best set (reps)", mode="lines+markers",
            line=dict(color=RED, width=3), marker=marker))
    _style(fig, f"{name}: progress", height=320)
    fig.update_layout(showlegend=True, margin=dict(l=10, r=10, t=48, b=40),
                      legend=dict(orientation="h", yanchor="top", y=-0.12, x=0))
    return fig


def _count_workouts(client, fallback: int) -> int:
    """Lifetime workout count (the dashboard only loads the last few months of rows)."""
    try:
        res = client.table("workouts").select("id", count="exact").limit(1).execute()
        return int(res.count) if res.count is not None else fallback
    except Exception:  # noqa: BLE001
        return fallback


def _targets_section(profile: dict, m: dict, data: dict) -> None:
    st.markdown("#### Today's targets")
    t = pg.daily_targets(profile, m["body"]["latest_weight_kg"])
    if not t:
        st.info("Fill in your profile (age, height, weight, goal) to get daily calorie and protein targets.")
        return
    eaten = pg.intake_on(data["meals"], date.today())
    cols = st.columns(4)
    for col, (label, key, unit) in zip(cols, [("Calories", "calories", "kcal"), ("Protein", "protein_g", "g"),
                                              ("Carbs", "carbs_g", "g"), ("Fat", "fat_g", "g")]):
        got, goal = eaten[key], t[key]
        col.metric(label, f"{got:,.0f} / {goal:,.0f} {unit}")
        col.progress(min(got / goal, 1.0) if goal else 0.0)
    note = f"Estimated from your profile and goal (maintenance is about {t['tdee']:,} kcal). A starting point, not medical advice."
    if not t["sex_known"]:
        note += " Set your sex in My profile for a better estimate."
    st.caption(note)


def _streaks_section(client, profile: dict, data: dict, m: dict) -> None:
    st.markdown("#### Streaks & achievements")
    today = date.today()
    workout_days = {pg.to_date(w["performed_on"]) for w in data["workouts"]}
    food_days = {pg.to_date(x["eaten_on"]) for x in data["meals"]}
    target = int(profile.get("days_per_week") or 3)
    wk_cur, wk_best = pg.weekly_streak(workout_days, target, today)
    log_cur, log_best = pg.daily_streak(workout_days | food_days, today)
    total = _count_workouts(client, len(data["workouts"]))

    c = st.columns(3)
    c[0].metric("Weekly streak", f"{wk_cur} wk",
                help=f"Consecutive weeks with {target}+ workouts. Your best: {wk_best}.")
    c[1].metric("Logging streak", f"{log_cur} d",
                help=f"Consecutive days with a workout or a meal logged. Your best: {log_best}.")
    c[2].metric("Total workouts", f"{total}")

    badges = pg.achievements({
        "total_workouts": total, "best_weekly_streak": wk_best, "best_logging_streak": log_best,
        "max_workout_volume": pg.max_workout_volume(data["sets"]), "food_days": len(food_days),
        "recent_prs": len(m["training"]["personal_records"]),
    })
    html = "".join(
        f'<div class="gc-ach{"" if b["earned"] else " locked"}"><div class="gc-ach-icon">{b["icon"]}</div>'
        f'<div><div class="gc-ach-title">{escape(b["title"])}</div>'
        f'<div class="gc-ach-desc">{escape(b["desc"])}</div>'
        f'<div class="gc-ach-prog">{escape(b["progress"])}</div></div></div>'
        for b in badges
    )
    st.markdown(f'<div class="gc-ach-grid">{html}</div>', unsafe_allow_html=True)


def _exercise_section(data: dict) -> None:
    names = pg.exercise_names(data["sets"])
    if not names:
        return
    st.markdown("#### Exercise progress")
    name = st.selectbox("Exercise", names, key="db_exercise", label_visibility="collapsed")
    hist = pg.exercise_history(data["sets"], name)
    st.plotly_chart(_exercise_chart(hist, name), width="stretch")
    e1rms = [h["e1rm"] for h in hist if h["e1rm"]]
    bits = [f"{len(hist)} session(s) in the last {HISTORY_DAYS // 30} months"]
    if e1rms:
        bits.insert(0, f"Best est. 1RM ≈ {max(e1rms):g} kg")
        bits.insert(1, f"top weight {max(h['top_weight'] for h in hist):g} kg")
    st.caption(" · ".join(bits))


def render(user) -> None:
    client = db.get_client()
    try:
        profile = an.get_profile(client, user.id)
        data = an.fetch_data(client, days=HISTORY_DAYS)
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

    _targets_section(profile, m, data)
    _streaks_section(client, profile, data, m)

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

    _exercise_section(data)

    st.markdown("#### Log body weight")
    _weight_form(client, user)
    pts = sorted((x["measured_on"], x["weight_kg"]) for x in data["body"] if x.get("weight_kg"))
    if len(pts) >= 2:
        st.plotly_chart(_weight_line(pts), width="stretch")