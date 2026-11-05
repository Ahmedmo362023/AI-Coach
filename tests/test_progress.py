"""Tests for utils/progress.py (no network, no keys)."""
from datetime import date, timedelta

from utils import progress as pg

TODAY = date(2026, 10, 11)  # a Sunday; its week starts Monday 2026-10-05


def d(s: str) -> date:
    return date.fromisoformat(s)


# ---------- daily targets ----------
PROFILE = {"age": 25, "height_cm": 170, "weight_kg": 70, "days_per_week": 4, "goal": "muscle_gain"}


def test_targets_male_muscle_gain():
    t = pg.daily_targets({**PROFILE, "sex": "male"})
    assert t["calories"] == 2800  # BMR 1642.5 x 1.55 x 1.10
    assert t["protein_g"] == 112  # 1.6 g/kg x 70 kg
    assert t["carbs_g"] > 0 and t["fat_g"] > 0
    assert t["sex_known"] is True


def test_targets_sex_ordering_and_unknown_is_in_between():
    male = pg.daily_targets({**PROFILE, "sex": "male"})["calories"]
    female = pg.daily_targets({**PROFILE, "sex": "female"})["calories"]
    unknown = pg.daily_targets(PROFILE)
    assert female < unknown["calories"] < male
    assert unknown["sex_known"] is False


def test_targets_never_below_bmr():
    p = {"age": 25, "height_cm": 170, "weight_kg": 70, "days_per_week": 1, "goal": "fat_loss", "sex": "male"}
    assert pg.daily_targets(p)["calories"] >= 1640  # BMR is 1642.5; floor applies


def test_targets_need_profile_data():
    assert pg.daily_targets({}) is None
    assert pg.daily_targets({"age": 25, "height_cm": 170}) is None
    # weight can come from the latest logged body weight instead of the profile
    assert pg.daily_targets({"age": 25, "height_cm": 170, "goal": "strength"}, weight_kg=80) is not None


def test_intake_on_sums_only_that_day():
    meals = [
        {"eaten_on": "2026-10-11", "calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 10},
        {"eaten_on": "2026-10-11", "calories": 250, "protein_g": None, "carbs_g": 20, "fat_g": 5},
        {"eaten_on": "2026-10-10", "calories": 999, "protein_g": 99, "carbs_g": 99, "fat_g": 99},
    ]
    got = pg.intake_on(meals, TODAY)
    assert got == {"calories": 750, "protein_g": 30, "carbs_g": 70, "fat_g": 15}


# ---------- streaks ----------
def test_weekly_streak_three_full_weeks():
    dates = [d(x) for x in (
        "2026-09-21", "2026-09-23", "2026-09-25",
        "2026-09-28", "2026-09-30", "2026-10-02",
        "2026-10-05", "2026-10-07", "2026-10-09",
    )]
    assert pg.weekly_streak(dates, 3, TODAY) == (3, 3)


def test_weekly_streak_current_week_in_progress_does_not_break_it():
    dates = [d(x) for x in (
        "2026-09-21", "2026-09-23", "2026-09-25",
        "2026-09-28", "2026-09-30", "2026-10-02",
        "2026-10-05",  # only 1 of 3 so far this week
    )]
    assert pg.weekly_streak(dates, 3, TODAY) == (2, 2)


def test_weekly_streak_resets_after_a_missed_week():
    dates = [d(x) for x in (
        "2026-09-21", "2026-09-23", "2026-09-25",
        "2026-09-28",  # week of Sep 28 missed the goal
        "2026-10-05", "2026-10-07", "2026-10-09",
    )]
    assert pg.weekly_streak(dates, 3, TODAY) == (1, 1)


def test_weekly_streak_last_week_missed_and_this_week_not_done():
    dates = [d("2026-09-21"), d("2026-09-23"), d("2026-09-25"), d("2026-10-05")]
    assert pg.weekly_streak(dates, 3, TODAY) == (0, 1)


def test_weekly_streak_empty():
    assert pg.weekly_streak([], 3, TODAY) == (0, 0)


def test_daily_streak_counts_today():
    days = {d("2026-10-09"), d("2026-10-10"), d("2026-10-11")}
    assert pg.daily_streak(days, TODAY) == (3, 3)


def test_daily_streak_today_empty_does_not_break():
    days = {d("2026-10-08"), d("2026-10-09"), d("2026-10-10")}
    assert pg.daily_streak(days, TODAY) == (3, 3)


def test_daily_streak_broken_but_best_is_kept():
    days = {d("2026-10-01"), d("2026-10-02"), d("2026-10-03"), d("2026-10-04"), d("2026-10-08")}
    assert pg.daily_streak(days, TODAY) == (0, 4)


def test_daily_streak_empty():
    assert pg.daily_streak([], TODAY) == (0, 0)


# ---------- exercise history ----------
SETS = [
    {"workout_id": "a", "performed_on": "2026-09-01", "exercise": "Bench Press", "reps": 8, "weight_kg": 60},
    {"workout_id": "a", "performed_on": "2026-09-01", "exercise": "bench  press", "reps": 5, "weight_kg": 70},
    {"workout_id": "b", "performed_on": "2026-09-08", "exercise": "Bench Press", "reps": 5, "weight_kg": 75},
    {"workout_id": "b", "performed_on": "2026-09-08", "exercise": "Squat", "reps": 5, "weight_kg": 100},
    {"workout_id": "b", "performed_on": "2026-09-08", "exercise": "Pull-up", "reps": 10, "weight_kg": None},
]


def test_exercise_names_group_case_and_spacing_most_trained_first():
    names = pg.exercise_names(SETS)
    assert names[0] == "Bench Press"
    assert set(names) == {"Bench Press", "Squat", "Pull-up"}


def test_exercise_history_per_day():
    h = pg.exercise_history(SETS, "Bench Press")
    assert [r["date"] for r in h] == ["2026-09-01", "2026-09-08"]
    assert h[0]["top_weight"] == 70
    assert h[0]["e1rm"] == round(70 * (1 + 5 / 30), 1)  # best of 60x8 and 70x5
    assert h[1]["top_weight"] == 75 and h[1]["sets"] == 1


def test_exercise_history_bodyweight_has_reps_but_no_e1rm():
    h = pg.exercise_history(SETS, "Pull-up")
    assert h[0]["top_reps"] == 10 and h[0]["e1rm"] is None and h[0]["top_weight"] == 0


def test_max_workout_volume():
    assert pg.max_workout_volume(SETS) == max(60 * 8 + 70 * 5, 75 * 5 + 100 * 5)
    assert pg.max_workout_volume([]) == 0


# ---------- achievements ----------
def test_achievements_earned_and_locked():
    badges = {b["title"]: b for b in pg.achievements({
        "total_workouts": 12, "best_weekly_streak": 2, "best_logging_streak": 7,
        "max_workout_volume": 4200, "food_days": 3, "recent_prs": 1,
    })}
    assert badges["First workout"]["earned"] and badges["10 workouts"]["earned"]
    assert not badges["50 workouts"]["earned"]
    assert badges["7-day logging"]["earned"]
    assert not badges["4-week streak"]["earned"] and badges["4-week streak"]["progress"] == "2/4 wk"
    assert not badges["10-ton session"]["earned"] and badges["10-ton session"]["progress"] == "4,200/10,000 kg"
    assert badges["New PR"]["earned"]
    assert not badges["Food tracker"]["earned"]


def test_achievements_nothing_yet():
    assert not any(b["earned"] for b in pg.achievements({}))