import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from streamlit.testing.v1 import AppTest

def _dash():
    import streamlit as st
    from datetime import date, timedelta
    from types import SimpleNamespace
    from tests.fakedb import FakeDB
    from utils import db
    if "fc" not in st.session_state:
        d = FakeDB(); t = date.today()
        d.tables["workouts"] = [{"id": "w1", "performed_on": t.isoformat()}]
        d.tables["workout_sets"] = [{"workout_id": "w1", "exercise": "Bench", "muscle_group": "chest", "reps": 5, "weight_kg": 70}]
        d.tables["meals"] = [{"eaten_on": t.isoformat(), "calories": 2000, "protein_g": 100, "carbs_g": 200, "fat_g": 60}]
        d.tables["body_metrics"] = [{"measured_on": (t - timedelta(days=1)).isoformat(), "weight_kg": 80}]
        st.session_state["fc"] = d
    db.get_client = lambda: st.session_state["fc"]
    from ui import dashboard_page
    dashboard_page.render(SimpleNamespace(id="u1", email="a@b.c"))

def _coach():
    import streamlit as st
    from types import SimpleNamespace
    from tests.fakedb import FakeDB
    from utils import db, llm
    if "fc" not in st.session_state: st.session_state["fc"] = FakeDB()
    db.get_client = lambda: st.session_state["fc"]
    seen = st.session_state.setdefault("seen", [])
    llm.coach_report = lambda metrics, chunks, lang: (seen.append((metrics, lang)) or "REPORT TEXT")
    from ui import coach_page
    coach_page.render(SimpleNamespace(id="u1", email="a@b.c"))

def test_dashboard_renders_metrics_and_logs_weight_and_profile():
    at = AppTest.from_function(_dash, default_timeout=30).run()
    assert not at.exception and not at.error, at.exception
    labels = {m.label: m.value for m in at.metric}
    assert labels["Sessions"] == "1" and labels["Weight"].startswith("80.0")
    at.number_input[-1].set_value(81.5)  # body weight field (last form)
    at.button[-1].click().run()          # "Log weight"
    assert not at.exception and not at.error
    labels = {m.label: m.value for m in at.metric}
    assert labels["Weight"].startswith("81.5")

def test_coach_generates_saves_and_lists():
    at = AppTest.from_function(_coach, default_timeout=30).run()
    assert not at.exception
    at.button(key="mr_coach_btn").click().run()
    assert not at.exception and not at.error, [e.value for e in at.error]
    assert any(m.value == "REPORT TEXT" for m in at.markdown)
    metrics, lang = at.session_state["seen"][0]
    assert metrics["training"]["sessions"] == 0 and lang.startswith("Egyptian")  # empty DB -> real zeros
    assert "No workouts logged this period." in metrics["flags"]
    at.run()  # past reports section lists the saved one
    assert any(e.label.count("→") for e in at.expander)
