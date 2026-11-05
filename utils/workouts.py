"""Workout data layer: validation, saving, reading. No Streamlit imports (easy to test)."""
from __future__ import annotations

import math
from datetime import date
from typing import Any


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _int(v: Any) -> int | None:
    f = _num(v)
    return None if f is None else int(round(f))


def normalize(rows_or_parsed: Any) -> list[dict]:
    """Clean model/editor output into valid set rows and renumber sets per exercise."""
    raw = rows_or_parsed.get("sets", []) if isinstance(rows_or_parsed, dict) else rows_or_parsed
    rows: list[dict] = []
    for s in raw or []:
        exercise = str(s.get("exercise") or "").strip()
        reps = _int(s.get("reps"))
        if not exercise or exercise.lower() == "nan" or not reps or reps <= 0:
            continue
        weight = _num(s.get("weight_kg"))
        rpe = _num(s.get("rpe"))
        group = str(s.get("muscle_group") or "").strip()
        rows.append(
            {
                "exercise": exercise,
                "muscle_group": group if group and group.lower() != "nan" else None,
                "reps": reps,
                "weight_kg": weight if weight is None or weight >= 0 else None,
                "rpe": rpe if rpe is None or 1 <= rpe <= 10 else None,
            }
        )
    counters: dict[str, int] = {}
    for r in rows:
        counters[r["exercise"]] = counters.get(r["exercise"], 0) + 1
        r["set_number"] = counters[r["exercise"]]
    return rows


def volume(rows: list[dict]) -> float:
    """Total tonnage = sum(weight * reps). Computed in code, never by the LLM."""
    return sum((r.get("weight_kg") or 0) * (r.get("reps") or 0) for r in rows)


def save_workout(client, user_id: str, performed_on: date, title: str | None,
                 raw_text: str, notes: str | None, rows: list[dict]) -> str:
    if not rows:
        raise ValueError("No valid sets to save.")
    w = (
        client.table("workouts")
        .insert(
            {
                "user_id": user_id,
                "performed_on": performed_on.isoformat(),
                "title": title or None,
                "raw_text": raw_text,
                "notes": notes or None,
            }
        )
        .execute()
    )
    workout_id = w.data[0]["id"]
    try:
        client.table("workout_sets").insert(
            [{**r, "workout_id": workout_id, "user_id": user_id} for r in rows]
        ).execute()
    except Exception:
        client.table("workouts").delete().eq("id", workout_id).execute()  # no half-saved workouts
        raise
    return workout_id


def fetch_recent(client, limit: int = 20) -> list[dict]:
    """Recent workouts, each with a 'sets' list."""
    ws = (
        client.table("workouts")
        .select("*")
        .order("performed_on", desc=True)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    if not ws:
        return []
    sets = (
        client.table("workout_sets")
        .select("*")
        .in_("workout_id", [w["id"] for w in ws])
        .order("created_at")
        .execute()
        .data
    )
    by_workout: dict[str, list[dict]] = {}
    for s in sets:
        by_workout.setdefault(s["workout_id"], []).append(s)
    for w in ws:
        w["sets"] = sorted(
            by_workout.get(w["id"], []), key=lambda s: (s["exercise"], s["set_number"])
        )
    return ws


def delete_workout(client, workout_id: str) -> None:
    client.table("workouts").delete().eq("id", workout_id).execute()
