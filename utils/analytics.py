"""Analytics engine. ALL numbers are computed here in code; the LLM only interprets them.

Pure functions on plain rows (lists of dicts) so they are easy to test. No Streamlit imports.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

MAIN_GROUPS = ["chest", "back", "shoulders", "legs"]
PROTEIN_G_PER_KG = {"fat_loss": 1.6, "muscle_gain": 1.6, "strength": 1.6, "general_fitness": 1.2}
GOAL_LABEL = {"fat_loss": "fat loss", "muscle_gain": "muscle gain", "strength": "strength",
              "general_fitness": "general fitness"}


def _d(v: Any) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _f(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def epley(weight: float, reps: int) -> float | None:
    """Estimated 1RM (Epley). Unreliable above ~12 reps, so those sets are ignored."""
    if not weight or weight <= 0 or not reps or reps <= 0 or reps > 12:
        return None
    return weight * (1 + reps / 30)


# ---------- training ----------
def _training(workouts: list[dict], sets: list[dict], start: date, end: date) -> dict:
    w_ids = {w["id"] for w in workouts if start <= _d(w["performed_on"]) <= end}
    s = [x for x in sets if start <= _d(x["performed_on"]) <= end]
    muscle: dict[str, int] = defaultdict(int)
    best: dict[str, float] = {}
    for x in s:
        muscle[(x.get("muscle_group") or "other")] += 1
        e = epley(_f(x.get("weight_kg")), int(_f(x.get("reps"))))
        if e and e > best.get(x["exercise"], 0):
            best[x["exercise"]] = e
    return {
        "sessions": len(w_ids),
        "sets": len(s),
        "volume_kg": round(sum(_f(x.get("weight_kg")) * _f(x.get("reps")) for x in s), 1),
        "sets_by_muscle": dict(sorted(muscle.items(), key=lambda kv: -kv[1])),
        "best_e1rm": {k: round(v, 1) for k, v in best.items()},
    }


def _prs(sets: list[dict], start: date, end: date) -> list[dict]:
    """Exercises whose best e1RM this period beats everything before it (needs history)."""
    before: dict[str, float] = {}
    now: dict[str, float] = {}
    for x in sets:
        e = epley(_f(x.get("weight_kg")), int(_f(x.get("reps"))))
        if not e:
            continue
        d = _d(x["performed_on"])
        if d < start:
            before[x["exercise"]] = max(before.get(x["exercise"], 0), e)
        elif d <= end:
            now[x["exercise"]] = max(now.get(x["exercise"], 0), e)
    return [
        {"exercise": ex, "e1rm_kg": round(e, 1), "previous_kg": round(before[ex], 1)}
        for ex, e in sorted(now.items())
        if ex in before and e > before[ex] + 0.01
    ]


# ---------- nutrition ----------
def _nutrition(meals: list[dict], start: date, end: date) -> dict:
    by_day: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for m in meals:
        d = _d(m["eaten_on"])
        if start <= d <= end:
            for f in ("calories", "protein_g", "carbs_g", "fat_g"):
                by_day[d][f] += _f(m.get(f))
    n = len(by_day)
    avg = {f: round(sum(v[f] for v in by_day.values()) / n, 1) if n else None
           for f in ("calories", "protein_g", "carbs_g", "fat_g")}
    return {"days_logged": n, **{f"avg_{k}": v for k, v in avg.items()}}


# ---------- main entry ----------
def compute_metrics(workouts, sets, meals, body, profile, today: date | None = None, days: int = 7) -> dict:
    today = today or date.today()
    profile = profile or {}
    cur_s, cur_e = today - timedelta(days=days - 1), today
    prev_e = cur_s - timedelta(days=1)
    prev_s = prev_e - timedelta(days=days - 1)

    train, train_prev = _training(workouts, sets, cur_s, cur_e), _training(workouts, sets, prev_s, prev_e)
    nut, nut_prev = _nutrition(meals, cur_s, cur_e), _nutrition(meals, prev_s, prev_e)
    prs = _prs(sets, cur_s, cur_e)

    pts = sorted(((_d(b["measured_on"]), _f(b["weight_kg"])) for b in body if b.get("weight_kg")))
    pts = [p for p in pts if p[0] <= today]
    latest_w = pts[-1][1] if pts else (_f(profile.get("weight_kg")) or None)
    ref = [p for p in pts if p[0] <= prev_e]
    weight_change = round(pts[-1][1] - ref[-1][1], 1) if pts and ref and pts[-1][0] > prev_e else None

    goal = profile.get("goal")
    target_sessions = profile.get("days_per_week")
    prev_vol = train_prev["volume_kg"]
    vol_change = round((train["volume_kg"] - prev_vol) / prev_vol * 100, 1) if prev_vol else None
    protein_per_kg = (round(nut["avg_protein_g"] / latest_w, 2)
                      if nut["avg_protein_g"] is not None and latest_w else None)

    flags: list[str] = []
    if train["sessions"] == 0:
        flags.append("No workouts logged this period.")
    elif target_sessions and train["sessions"] < target_sessions:
        flags.append(f"{train['sessions']} of {target_sessions} planned sessions done.")
    if train["sessions"]:
        missing = [g for g in MAIN_GROUPS if train["sets_by_muscle"].get(g, 0) == 0]
        if missing:
            flags.append("No sets for: " + ", ".join(missing) + ".")
    if vol_change is not None and vol_change > 30:
        flags.append(f"Training volume up {vol_change:.0f}% vs the previous period: watch recovery.")
    if nut["days_logged"] < 3:
        flags.append(f"Only {nut['days_logged']} day(s) of food logged: nutrition averages are unreliable.")
    target_p = PROTEIN_G_PER_KG.get(goal)
    if target_p and protein_per_kg is not None and nut["days_logged"] >= 3 and protein_per_kg < target_p * 0.85:
        flags.append(f"Protein {protein_per_kg} g/kg is below the usual {target_p} g/kg guideline for this goal.")
    if weight_change is not None:
        if goal == "fat_loss" and weight_change > 0.2:
            flags.append(f"Weight up {weight_change} kg while the goal is fat loss.")
        if goal == "muscle_gain" and weight_change < -0.2:
            flags.append(f"Weight down {abs(weight_change)} kg while the goal is muscle gain.")

    return {
        "period": {"start": cur_s.isoformat(), "end": cur_e.isoformat(), "days": days,
                   "previous_start": prev_s.isoformat(), "previous_end": prev_e.isoformat()},
        "profile": {"goal": GOAL_LABEL.get(goal, goal), "experience": profile.get("experience"),
                    "planned_sessions_per_week": target_sessions, "weight_kg": latest_w},
        "training": {**train, "previous": {k: train_prev[k] for k in ("sessions", "sets", "volume_kg")},
                     "volume_change_pct": vol_change, "personal_records": prs},
        "nutrition": {**nut, "previous": {k: v for k, v in nut_prev.items() if k != "days_logged"}
                      | {"days_logged": nut_prev["days_logged"]},
                      "protein_g_per_kg": protein_per_kg},
        "body": {"latest_weight_kg": latest_w, "change_vs_previous_period_kg": weight_change},
        "flags": flags,
    }


# ---------- chart series ----------
def weekly_volume_series(sets: list[dict], today: date | None = None, weeks: int = 8) -> list[dict]:
    today = today or date.today()
    out = []
    for i in range(weeks - 1, -1, -1):
        end = today - timedelta(days=7 * i)
        start = end - timedelta(days=6)
        t = _training([], [x for x in sets], start, end)
        out.append({"week_ending": end.isoformat(), "volume_kg": t["volume_kg"], "sets": t["sets"]})
    return out


def daily_nutrition_series(meals: list[dict], today: date | None = None, days: int = 14) -> list[dict]:
    today = today or date.today()
    totals: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for m in meals:
        d = _d(m["eaten_on"])
        totals[d]["calories"] += _f(m.get("calories"))
        totals[d]["protein_g"] += _f(m.get("protein_g"))
    out = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        t = totals.get(d)
        out.append({"day": d.isoformat(), "calories": round(t["calories"]) if t else None,
                    "protein_g": round(t["protein_g"]) if t else None})
    return out


# ---------- data access ----------
def fetch_data(client, today: date | None = None, days: int = 90) -> dict:
    """Workouts, sets (each tagged with performed_on), meals, body metrics for the last `days`."""
    today = today or date.today()
    since = (today - timedelta(days=days)).isoformat()
    workouts = (client.table("workouts").select("id,performed_on,title")
                .gte("performed_on", since).limit(1000).execute().data)
    date_of = {w["id"]: w["performed_on"] for w in workouts}
    sets: list[dict] = []
    ids = list(date_of)
    for i in range(0, len(ids), 50):
        rows = (client.table("workout_sets").select("workout_id,exercise,muscle_group,reps,weight_kg")
                .in_("workout_id", ids[i:i + 50]).limit(5000).execute().data)
        sets += [{**r, "performed_on": date_of[r["workout_id"]]} for r in rows]
    meals = (client.table("meals").select("eaten_on,calories,protein_g,carbs_g,fat_g")
             .gte("eaten_on", since).limit(5000).execute().data)
    body = (client.table("body_metrics").select("measured_on,weight_kg")
            .gte("measured_on", since).limit(1000).execute().data)
    return {"workouts": workouts, "sets": sets, "meals": meals, "body": body}


def get_profile(client, user_id: str) -> dict:
    rows = client.table("profiles").select("*").eq("id", user_id).execute().data
    return rows[0] if rows else {}


def save_profile(client, user_id: str, **fields) -> None:
    client.table("profiles").upsert({"id": user_id, **fields}).execute()


def add_weight(client, user_id: str, measured_on: date, weight_kg: float) -> None:
    if not 25 <= weight_kg <= 400:
        raise ValueError("Weight must be between 25 and 400 kg.")
    client.table("body_metrics").insert(
        {"user_id": user_id, "measured_on": measured_on.isoformat(), "weight_kg": weight_kg}
    ).execute()


def save_report(client, user_id: str, metrics: dict, text: str) -> None:
    client.table("coach_reports").insert({
        "user_id": user_id, "period_start": metrics["period"]["start"],
        "period_end": metrics["period"]["end"], "metrics": metrics, "report_text": text,
    }).execute()


def list_reports(client, limit: int = 20) -> list[dict]:
    return (client.table("coach_reports").select("id,period_start,period_end,report_text,created_at")
            .order("created_at", desc=True).limit(limit).execute().data)
