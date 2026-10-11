import streamlit as st

from utils import db
from utils.theme import brand, features, hero, inject_theme, page_header, panel, user_chip

st.set_page_config(page_title="GymCoachAI", page_icon="🔥", layout="wide")
inject_theme()


# ---------- Auth ----------
def auth_screen() -> None:
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        brand()
        hero("Train smarter.", "Recover better.")
        st.markdown(
            '<p class="gc-sub">Log your lifts and meals in plain language. Your coach reads your '
            "numbers and your medical report before it plans your week.</p>",
            unsafe_allow_html=True,
        )
        features([
            ("Workout tracker", "Say it the way you'd tell a friend. It becomes sets, reps and weights."),
            ("Food log", "Calories and macros for what you ate, ready to edit."),
            ("Medical-aware coach", "Upload your report as text or PDF and your plan adapts to it."),
        ])

    with right:
        with panel("auth"):
            tab_in, tab_up = st.tabs(["Log in", "Sign up"])
            with tab_in:
                with st.form("login", border=False):
                    email = st.text_input("Email")
                    pwd = st.text_input("Password", type="password")
                    ok = st.form_submit_button("Log in", type="primary", width="stretch")
                if ok:
                    try:
                        res = db.sign_in(email, pwd)
                        st.session_state["user"] = res.user
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Login failed: {e}")
            with tab_up:
                with st.form("signup", border=False):
                    name = st.text_input("Full name")
                    email = st.text_input("Email", key="su_email")
                    pwd = st.text_input("Password (min 6 chars)", type="password", key="su_pwd")
                    ok = st.form_submit_button("Create account", type="primary", width="stretch")
                if ok:
                    try:
                        res = db.sign_up(email, pwd, name)
                        if res.session:
                            st.session_state["user"] = res.user
                            st.rerun()
                        st.success("Account created. Check your email to confirm, then log in.")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Sign up failed: {e}")


# ---------- Main app ----------
PAGES = ["Dashboard", "Workout Log", "Nutrition", "Medical Report", "AI Coach"]
ICONS = {
    "Dashboard": "dashboard",
    "Workout Log": "fitness_center",
    "Nutrition": "restaurant",
    "Medical Report": "clinical_notes",
    "AI Coach": "insights",
}
SUBTITLES = {
    "Dashboard": "Your last 7 days: training, food and body weight.",
    "Workout Log": "Write your session the way you'd tell a friend. It becomes sets, reps and weights.",
    "Nutrition": "Log what you ate. Calories and macros are estimates, and you can edit them.",
    "Medical Report": "Add your report, ask it questions, and adjust your plan around it.",
    "AI Coach": "A weekly review built from your own numbers.",
}


def main_app() -> None:
    user = st.session_state["user"]
    # The page lives in the URL (?page=...) so a browser refresh stays on the same page.
    if "nav_page" not in st.session_state:
        wanted = st.query_params.get("page")
        st.session_state["nav_page"] = wanted if wanted in PAGES else PAGES[0]
    with st.sidebar:
        brand()
        user_chip(user)
        page = st.radio(
            "Navigate",
            PAGES,
            key="nav_page",
            format_func=lambda p: f":material/{ICONS[p]}: {p}",
            label_visibility="collapsed",
        )
        st.divider()
        if st.button("Log out", width="stretch", icon=":material/logout:"):
            db.sign_out()
            st.rerun()

    if st.query_params.get("page") != page:
        st.query_params["page"] = page
    page_header(page, SUBTITLES[page])
    if page == "Workout Log":
        from ui import workout_page

        workout_page.render(user)
    elif page == "Nutrition":
        from ui import nutrition_page

        nutrition_page.render(user)
    elif page == "Medical Report":
        from ui import medical_page

        medical_page.render(user)
    elif page == "AI Coach":
        from ui import coach_page

        coach_page.render(user)
    else:
        from ui import dashboard_page

        dashboard_page.render(user)


# Order matters: the cookie component must exist on every run, before we try to restore.
try:
    db.get_client()
except RuntimeError as err:
    st.error(str(err))
    st.stop()

db.init_cookies()
db.restore_session()      # after a browser refresh: log back in from the cookie
if "user" not in st.session_state:
    db.wait_for_cookies()  # the cookie arrives one rerun late; wait once, no login flash
    auth_screen()
else:
    db.sync_cookie()       # keep the cookie equal to the (rotating) refresh token
    main_app()