"""Coach chat helpers: build the data context in code, trim history, rate-limit.

No Streamlit and no LLM calls here (easy to test). The LLM only explains these numbers.
"""
from __future__ import annotations

import re
import time
from datetime import date, timedelta

from utils import analytics as an
from utils import progress as pg

MAX_QUESTION_CHARS = 600
HISTORY_TURNS = 8          # last N messages sent to the model
MAX_MESSAGES = 60          # hard cap per conversation
RATE_LIMIT = 8             # questions ...
RATE_WINDOW = 300          # ... per 5 minutes, per session

# Only pay for a report search when the question is about health / the report.
MEDICAL_RE = re.compile(
    r"(report|mri|x-?ray|injur|pain|hurt|disc|herni|knee|back|shoulder|doctor|heart|pressure|diabet|sugar|"
    r"cholesterol|surgery|medic|allerg|تقرير|اشعة|أشعة|رنين|اصاب|إصاب|وجع|الم|ألم|ركبة|ضهر|ظهر|كتف|غضروف|"
    r"دكتور|دكتوره|طبيب|قلب|ضغط|سكر|كوليسترول|عملية|دوا|علاج)",
    re.IGNORECASE,
)


def clean_question(q: str) -> str:
    return " ".join((q or "").split())[:MAX_QUESTION_CHARS]


def wants_report(question: str) -> bool:
    return bool(MEDICAL_RE.search(question or ""))


def trim_history(messages: list[dict], turns: int = HISTORY_TURNS) -> list[dict]:
    keep = [{"role": m["role"], "content": m["content"]} for m in messages
            if m.get("role") in ("user", "assistant") and m.get("content")]
    return keep[-turns:]


def rate_limited(stamps: list[float], now: float | None = None,
                 limit: int = RATE_LIMIT, window: int = RATE_WINDOW) -> tuple[bool, int]:
    """(blocked, seconds_to_wait). `stamps` holds past request times."""
    now = time.time() if now is None else now
    recent = sorted(t for t in stamps if now - t < window)
    if len(recent) >= limit:
        return True, int(window - (now - recent[0])) + 1
    return False, 0


def build_context(profile: dict, data: dict, today: date | None = None) -> dict:
    """Everything the coach may quote, computed from the user's own rows."""
    today = today or date.today()
    profile = profile or {}
    metrics = an.compute_metrics(data["workouts"], data["sets"], data["meals"], data["body"],
                                 profile, today=today)
    weight = metrics["body"]["latest_weight_kg"]
    targets = pg.daily_targets(profile, weight)
    if targets:
        targets = {k: v for k, v in targets.items() if k != "sex_known"}
    intake = {k: round(v) for k, v in pg.intake_on(data["meals"], today).items()}

    w_dates = [pg.to_date(w["performed_on"]) for w in data["workouts"]]
    planned = profile.get("days_per_week") or 3
    wk_cur, wk_best = pg.weekly_streak(w_dates, planned, today)
    log_days = {pg.to_date(m["eaten_on"]) for m in data["meals"]}
    lg_cur, lg_best = pg.daily_streak(log_days, today)

    # best estimated 1RM per exercise over the loaded history (top 6 most recent exercises)
    lifts = []
    for name in pg.exercise_names(data["sets"])[:6]:
        hist = pg.exercise_history(data["sets"], name)
        if hist:
            lifts.append({"exercise": name, "history": hist[-4:]})

    recent = sorted(data["workouts"], key=lambda w: str(w["performed_on"]), reverse=True)[:5]
    return {
        "today": today.isoformat(),
        "last_7_days": metrics,
        "daily_targets": targets,
        "intake_today": intake,
        "streaks": {"weekly_current": wk_cur, "weekly_best": wk_best,
                    "food_logging_current": lg_cur, "food_logging_best": lg_best},
        "recent_workouts": [{"date": str(w["performed_on"])[:10], "title": w.get("title")} for w in recent],
        "exercise_progress": lifts,
    }