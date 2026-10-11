"""Daily targets, streaks, achievements and per-exercise history.

Pure functions on plain rows (lists of dicts). No Streamlit, no database: easy to test.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any, Iterable

from utils.analytics import PROTEIN_G_PER_KG, epley


def to_date(v: Any) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _f(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ---------- daily targets ----------
# Calories: Mifflin-St Jeor BMR x an activity factor taken from planned sessions per week,
# then nudged by goal. Protein uses the same g/kg guideline as the analytics engine.
GOAL_ADJUST = {"fat_loss": -0.20, "muscle_gain": 0.10, "strength": 0.05, "general_fitness": 0.0}
SEX_OFFSET = {"male": 5, "female": -161}
SEX_OFFSET_UNKNOWN = -78  # midpoint, used until the user sets their sex


def activity_factor(days_per_week: Any) -> float:
    d = int(_f(days_per_week)) or 3
    if d <= 1:
        return 1.2
    if d <= 3:
        return 1.375
    if d <= 5:
        return 1.55
    return 1.725


def daily_targets(profile: dict, weight_kg: float | None = None) -> dict | None:
    """Estimated daily calories/protein/carbs/fat. None when age, height or weight is missing."""
    profile = profile or {}
    w = _f(weight_kg) or _f(profile.get("weight_kg"))
    h, a = _f(profile.get("height_cm")), _f(profile.get("age"))
    if not (w and h and a):
        return None
    sex = profile.get("sex")
    bmr = 10 * w + 6.25 * h - 5 * a + SEX_OFFSET.get(sex, SEX_OFFSET_UNKNOWN)
    tdee = bmr * activity_factor(profile.get("days_per_week"))
    goal = profile.get("goal")
    calories = max(tdee * (1 + GOAL_ADJUST.get(goal, 0.0)), bmr)  # never eat below BMR
    protein = PROTEIN_G_PER_KG.get(goal, 1.2) * w
    fat = 0.25 * calories / 9
    carbs = max(calories - protein * 4 - fat * 9, 0) / 4
    return {
        "calories": int(round(calories / 10) * 10),
        "protein_g": int(round(protein)),
        "carbs_g": int(round(carbs)),
        "fat_g": int(round(fat)),
        "tdee": int(round(tdee / 10) * 10),
        "sex_known": sex in SEX_OFFSET,
    }


def intake_on(meals: Iterable[dict], day: date) -> dict[str, float]:
    """What was eaten on `day`, summed in code."""
    out = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for m in meals:
        if to_date(m["eaten_on"]) == day:
            for k in out:
                out[k] += _f(m.get(k))
    return out


# ---------- streaks ----------
def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def weekly_streak(workout_dates: Iterable[date], target: int, today: date) -> tuple[int, int]:
    """(current, best) run of consecutive weeks (Mon-Sun) with at least `target` sessions.

    The week in progress never breaks the streak: it only adds to it once the goal is met.
    """
    target = max(int(target or 3), 1)
    counts = Counter(_week_start(d) for d in workout_dates)
    if not counts:
        return 0, 0
    this_week = _week_start(today)
    weeks: list[bool] = []
    w = min(counts)
    while w <= this_week:
        weeks.append(counts.get(w, 0) >= target)
        w += timedelta(days=7)
    best = run = 0
    for ok in weeks:
        run = run + 1 if ok else 0
        best = max(best, run)
    i = len(weeks) - 1
    if not weeks[i]:  # current week not done yet: look at the completed weeks before it
        i -= 1
    cur = 0
    while i >= 0 and weeks[i]:
        cur += 1
        i -= 1
    return cur, best


def daily_streak(days: Iterable[date], today: date) -> tuple[int, int]:
    """(current, best) run of consecutive days. Today may still be empty without breaking it."""
    s = set(days)
    if not s:
        return 0, 0
    d = today if today in s else today - timedelta(days=1)
    cur = 0
    while d in s:
        cur += 1
        d -= timedelta(days=1)
    best = run = 0
    prev = None
    for d in sorted(s):
        run = run + 1 if prev is not None and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return cur, best


# ---------- per-exercise history ----------
def _key(name: Any) -> str:
    return " ".join(str(name or "").lower().split())


def exercise_names(sets: Iterable[dict]) -> list[str]:
    """Distinct exercises, most-trained first. 'Bench Press' and 'bench  press' are one exercise."""
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for s in sets:
        k = _key(s.get("exercise"))
        if k:
            counts[k] += 1
            display.setdefault(k, " ".join(str(s["exercise"]).split()))
    return [display[k] for k, _ in counts.most_common()]


def exercise_history(sets: Iterable[dict], exercise: str) -> list[dict]:
    """One row per training day: top weight, top reps, best estimated 1RM, volume."""
    k = _key(exercise)
    by_day: dict[date, dict] = {}
    for s in sets:
        if _key(s.get("exercise")) != k:
            continue
        d = to_date(s["performed_on"])
        w, r = _f(s.get("weight_kg")), int(_f(s.get("reps")))
        rec = by_day.setdefault(
            d, {"date": d.isoformat(), "top_weight": 0.0, "top_reps": 0, "e1rm": 0.0, "volume": 0.0, "sets": 0}
        )
        rec["top_weight"] = max(rec["top_weight"], w)
        rec["top_reps"] = max(rec["top_reps"], r)
        e = epley(w, r)
        if e:
            rec["e1rm"] = max(rec["e1rm"], e)
        rec["volume"] += w * r
        rec["sets"] += 1
    out = []
    for d in sorted(by_day):
        rec = by_day[d]
        rec["e1rm"] = round(rec["e1rm"], 1) or None
        rec["top_weight"] = round(rec["top_weight"], 1)
        rec["volume"] = round(rec["volume"], 1)
        out.append(rec)
    return out


def max_workout_volume(sets: Iterable[dict]) -> float:
    """Biggest total tonnage in a single workout."""
    per: dict[Any, float] = {}
    for s in sets:
        wid = s.get("workout_id")
        per[wid] = per.get(wid, 0.0) + _f(s.get("weight_kg")) * _f(s.get("reps"))
    return max(per.values(), default=0.0)


# ---------- achievements ----------
def achievements(stats: dict) -> list[dict]:
    """Badges computed from the data (nothing is stored). Each: icon, title, desc, earned, progress."""
    total = int(_f(stats.get("total_workouts")))
    best_week = int(_f(stats.get("best_weekly_streak")))
    best_log = int(_f(stats.get("best_logging_streak")))
    max_vol = _f(stats.get("max_workout_volume"))
    food_days = int(_f(stats.get("food_days")))
    prs = int(_f(stats.get("recent_prs")))

    def tier(icon: str, title: str, desc: str, value: float, goal: float, unit: str = "") -> dict:
        return {
            "icon": icon, "title": title, "desc": desc, "earned": value >= goal,
            "progress": f"{min(value, goal):,.0f}/{goal:,.0f}{unit}",
        }

    return [
        tier("💪", "First workout", "Log your first workout", total, 1),
        tier("🔟", "10 workouts", "Log 10 workouts", total, 10),
        tier("🏋️", "50 workouts", "Log 50 workouts", total, 50),
        tier("🔥", "4-week streak", "Hit your weekly session goal 4 weeks in a row", best_week, 4, " wk"),
        tier("📅", "7-day logging", "Log a workout or a meal 7 days in a row", best_log, 7, " d"),
        tier("⚡", "10-ton session", "Lift 10,000 kg of volume in one workout", max_vol, 10000, " kg"),
        {"icon": "🏆", "title": "New PR", "desc": "Beat a personal record in the last 7 days",
         "earned": prs > 0, "progress": "this week" if prs > 0 else "none yet"},
        tier("🍽️", "Food tracker", "Log your food on 7 different days", food_days, 7, " d"),
    ]