"""Nutrition data layer: validation, totals, saving, reading. No Streamlit imports."""
from __future__ import annotations

from datetime import date
from typing import Any

from utils.workouts import _num

MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack", "other"]
MACRO_FIELDS = ["calories", "protein_g", "carbs_g", "fat_g"]


def normalize(rows_or_parsed: Any) -> list[dict]:
    """Clean model/editor output into valid meal rows (never negative, never NaN)."""
    raw = rows_or_parsed.get("meals", []) if isinstance(rows_or_parsed, dict) else rows_or_parsed
    rows: list[dict] = []
    for m in raw or []:
        name = str(m.get("name") or "").strip()
        if not name or name.lower() == "nan":
            continue
        meal_type = str(m.get("meal_type") or "").strip().lower()
        row = {"meal_type": meal_type if meal_type in MEAL_TYPES else "other", "name": name}
        for f in MACRO_FIELDS:
            v = _num(m.get(f))
            row[f] = v if v is not None and v >= 0 else None
        # An item with no numbers at all isn't useful to track
        if all(row[f] is None for f in MACRO_FIELDS):
            continue
        rows.append(row)
    return rows


def totals(rows: list[dict]) -> dict[str, float]:
    """Daily totals, computed in code (never by the LLM). Missing values count as 0."""
    return {f: sum((r.get(f) or 0) for r in rows) for f in MACRO_FIELDS}


def macro_calories(row: dict) -> float:
    """Calories implied by macros (4/4/9). Used to flag inconsistent estimates."""
    return 4 * (row.get("protein_g") or 0) + 4 * (row.get("carbs_g") or 0) + 9 * (row.get("fat_g") or 0)


def inconsistent(row: dict, tolerance: float = 0.35) -> bool:
    """True when stated calories differ a lot from what the macros imply."""
    cal, implied = row.get("calories"), macro_calories(row)
    if cal is None or implied == 0:
        return False
    return abs(cal - implied) / max(cal, implied) > tolerance


def save_meals(client, user_id: str, eaten_on: date, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("No valid items to save.")
    client.table("meals").insert(
        [{**r, "user_id": user_id, "eaten_on": eaten_on.isoformat()} for r in rows]
    ).execute()


def fetch_days(client, max_items: int = 400) -> list[dict]:
    """Recent meals grouped by day: [{'day': 'YYYY-MM-DD', 'items': [...], 'totals': {...}}]."""
    items = (
        client.table("meals")
        .select("*")
        .order("eaten_on", desc=True)
        .order("created_at", desc=True)
        .limit(max_items)
        .execute()
        .data
    )
    days: dict[str, list[dict]] = {}
    for it in items:
        days.setdefault(str(it["eaten_on"]), []).append(it)
    return [{"day": d, "items": its, "totals": totals(its)} for d, its in days.items()]


def delete_meal(client, meal_id: str) -> None:
    client.table("meals").delete().eq("id", meal_id).execute()
