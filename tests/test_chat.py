from datetime import date, timedelta

from utils import chat

T = date(2026, 10, 11)


def ds(n):
    return (T - timedelta(days=n)).isoformat()


def data():
    ws = [{"id": f"w{i}", "performed_on": ds(n), "title": "Chest"} for i, n in enumerate([1, 3, 5])]
    sets = [{"workout_id": f"w{i}", "exercise": "Bench Press", "muscle_group": "chest", "reps": 8,
             "weight_kg": 60 + i, "performed_on": ds(n)} for i, n in enumerate([1, 3, 5])]
    meals = [{"eaten_on": T.isoformat(), "calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 10}]
    return {"workouts": ws, "sets": sets, "meals": meals, "body": [{"measured_on": ds(2), "weight_kg": 70}]}


PROFILE = {"goal": "muscle_gain", "experience": "intermediate", "days_per_week": 3,
           "age": 25, "height_cm": 170, "weight_kg": 70, "sex": "male"}


def test_context_has_real_numbers():
    c = chat.build_context(PROFILE, data(), T)
    assert c["intake_today"]["calories"] == 500
    assert c["daily_targets"]["calories"] > 1500 and "sex_known" not in c["daily_targets"]
    assert c["last_7_days"]["training"]["sessions"] == 3
    assert c["exercise_progress"][0]["exercise"] == "Bench Press"
    assert len(c["recent_workouts"]) == 3
    assert c["streaks"]["food_logging_current"] == 1


def test_context_without_profile_or_data():
    c = chat.build_context({}, {"workouts": [], "sets": [], "meals": [], "body": []}, T)
    assert c["daily_targets"] is None and c["exercise_progress"] == []


def test_wants_report():
    assert chat.wants_report("my knee hurts, what about my MRI?")
    assert chat.wants_report("عندي وجع في الضهر")
    assert not chat.wants_report("how much protein today?")


def test_clean_and_trim():
    assert chat.clean_question("  a   b\n c ") == "a b c"
    assert len(chat.clean_question("x" * 5000)) == chat.MAX_QUESTION_CHARS
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i), "extra": 1} for i in range(20)]
    t = chat.trim_history(msgs)
    assert len(t) == chat.HISTORY_TURNS and t[-1]["content"] == "19" and "extra" not in t[0]


def test_rate_limit():
    now = 1000.0
    assert chat.rate_limited([], now) == (False, 0)
    stamps = [now - 10 * i for i in range(chat.RATE_LIMIT)]
    blocked, wait = chat.rate_limited(stamps, now)
    assert blocked and 0 < wait <= chat.RATE_WINDOW
    assert chat.rate_limited([now - 1000] * 20, now) == (False, 0)