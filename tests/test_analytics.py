import os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from utils import analytics as an
from tests.fakedb import FakeDB

TODAY = date(2026, 10, 10)
W = [{"id": "w0", "performed_on": "2026-09-01"}, {"id": "w3", "performed_on": "2026-10-01"},
     {"id": "w1", "performed_on": "2026-10-08"}, {"id": "w2", "performed_on": "2026-10-05"}]
def S(wid, d, ex, grp, reps, kg): return {"workout_id": wid, "performed_on": d, "exercise": ex, "muscle_group": grp, "reps": reps, "weight_kg": kg}
SETS = [S("w0", "2026-09-01", "Bench", "chest", 5, 60),
        S("w3", "2026-10-01", "Bench", "chest", 10, 60), S("w3", "2026-10-01", "Squat", "legs", 5, 100),
        S("w1", "2026-10-08", "Bench", "chest", 5, 70), S("w1", "2026-10-08", "Bench", "chest", 5, 70),
        S("w2", "2026-10-05", "Row", "back", 10, 50)]
MEALS = [{"eaten_on": "2026-10-08", "calories": 1200, "protein_g": 60, "carbs_g": 100, "fat_g": 40},
         {"eaten_on": "2026-10-08", "calories": 800, "protein_g": 40, "carbs_g": 80, "fat_g": 20},
         {"eaten_on": "2026-10-09", "calories": 2200, "protein_g": 120, "carbs_g": 200, "fat_g": 70}]
BODY = [{"measured_on": "2026-10-02", "weight_kg": 80.0}, {"measured_on": "2026-10-09", "weight_kg": 80.6}]
PROFILE = {"goal": "muscle_gain", "days_per_week": 4, "weight_kg": 75, "experience": "intermediate"}

def test_epley():
    assert an.epley(60, 5) == pytest.approx(70.0)
    assert an.epley(60, 13) is None and an.epley(0, 5) is None and an.epley(60, 0) is None

def test_metrics_hand_computed():
    m = an.compute_metrics(W, SETS, MEALS, BODY, PROFILE, today=TODAY)
    t = m["training"]
    assert (t["sessions"], t["sets"], t["volume_kg"]) == (2, 3, 1200.0)
    assert t["previous"] == {"sessions": 1, "sets": 2, "volume_kg": 1100.0}
    assert t["volume_change_pct"] == 9.1
    assert t["sets_by_muscle"] == {"chest": 2, "back": 1}
    assert t["personal_records"] == [{"exercise": "Bench", "e1rm_kg": 81.7, "previous_kg": 80.0}]
    n = m["nutrition"]
    assert n["days_logged"] == 2 and n["avg_calories"] == 2100.0 and n["avg_protein_g"] == 110.0
    assert m["body"]["latest_weight_kg"] == 80.6 and m["body"]["change_vs_previous_period_kg"] == 0.6
    assert n["protein_g_per_kg"] == pytest.approx(110 / 80.6, abs=0.01)
    assert m["period"]["start"] == "2026-10-04" and m["period"]["previous_end"] == "2026-10-03"

def test_flags():
    f = an.compute_metrics(W, SETS, MEALS, BODY, PROFILE, today=TODAY)["flags"]
    assert "2 of 4 planned sessions done." in f
    assert "No sets for: shoulders, legs." in f
    assert any("Only 2 day(s) of food logged" in x for x in f)
    assert not any("Protein" in x for x in f)  # too few days to judge protein

def test_low_protein_and_weight_flags():
    meals = [{"eaten_on": f"2026-10-0{d}", "calories": 1800, "protein_g": 60, "carbs_g": 200, "fat_g": 50} for d in (6, 7, 8)]
    f = an.compute_metrics(W, SETS, meals, BODY, {**PROFILE, "goal": "fat_loss"}, today=TODAY)["flags"]
    assert any("below the usual 1.6 g/kg" in x for x in f)
    assert "Weight up 0.6 kg while the goal is fat loss." in f

def test_empty_and_no_profile():
    m = an.compute_metrics([], [], [], [], None, today=TODAY)
    assert m["training"]["sessions"] == 0 and m["nutrition"]["avg_calories"] is None
    assert m["training"]["volume_change_pct"] is None and m["body"]["latest_weight_kg"] is None
    assert "No workouts logged this period." in m["flags"]

def test_volume_jump_flag():
    sets = SETS + [S("w1", "2026-10-08", "Squat", "legs", 5, 200)]
    f = an.compute_metrics(W, sets, [], [], PROFILE, today=TODAY)["flags"]
    assert any("volume up" in x for x in f)

def test_series():
    wk = an.weekly_volume_series(SETS, TODAY, weeks=2)
    assert [r["volume_kg"] for r in wk] == [1100.0, 1200.0]
    d = an.daily_nutrition_series(MEALS, TODAY, days=3)
    assert [r["calories"] for r in d] == [2000, 2200, None]  # 10-08, 10-09, 10-10 (not logged)

def test_fetch_data_tags_dates_and_window():
    db = FakeDB()
    db.tables["workouts"] = [{"id": "a", "performed_on": "2026-10-08"}, {"id": "old", "performed_on": "2025-01-01"}]
    db.tables["workout_sets"] = [{"workout_id": "a", "exercise": "Bench", "reps": 5, "weight_kg": 70},
                                 {"workout_id": "old", "exercise": "Bench", "reps": 5, "weight_kg": 90}]
    d = an.fetch_data(db, TODAY, days=90)
    assert [w["id"] for w in d["workouts"]] == ["a"]
    assert d["sets"] == [{"workout_id": "a", "exercise": "Bench", "reps": 5, "weight_kg": 70, "performed_on": "2026-10-08"}]

def test_profile_weight_report_roundtrip():
    db = FakeDB()
    assert an.get_profile(db, "u1") == {}
    an.save_profile(db, "u1", goal="fat_loss", days_per_week=3)
    an.save_profile(db, "u1", days_per_week=5)
    assert an.get_profile(db, "u1")["days_per_week"] == 5
    an.add_weight(db, "u1", TODAY, 81.2)
    with pytest.raises(ValueError): an.add_weight(db, "u1", TODAY, 5)
    m = an.compute_metrics(W, SETS, MEALS, BODY, PROFILE, today=TODAY)
    an.save_report(db, "u1", m, "text")
    assert an.list_reports(db)[0]["report_text"] == "text"
