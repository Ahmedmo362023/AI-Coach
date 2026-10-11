import streamlit as st

from utils.theme import card, inject_theme
from utils import db

st.set_page_config(page_title="GymCoachAI", page_icon="🔥", layout="wide")
inject_theme()


# ---------- Auth ----------
def auth_screen() -> None:
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown(
            '<div class="gc-hero">Train smarter.<br>Recover <span>better</span>.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="gc-muted" style="margin-top:1rem">'
            "Log your lifts in plain language, track your meals, and get a coach that "
            "reads your numbers and your medical report before it plans your week.</p>",
            unsafe_allow_html=True,
        )
        card("Workout tracker", "Say it like you'd tell a friend — we structure it.", "Tracker")
        card("Smart plans", "Training and nutrition plans built from your data.", "AI Coach")
        card("Medical-aware", "Upload your report as text/PDF and plans adapt to it.", "RAG")

    with right:
        tab_in, tab_up = st.tabs(["Log in", "Sign up"])
        with tab_in:
            with st.form("login"):
                email = st.text_input("Email")
                pwd = st.text_input("Password", type="password")
                ok = st.form_submit_button("Log in", width="stretch")
            if ok:
                try:
                    res = db.sign_in(email, pwd)
                    st.session_state["user"] = res.user
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Login failed: {e}")
        with tab_up:
            with st.form("signup"):
                name = st.text_input("Full name")
                email = st.text_input("Email", key="su_email")
                pwd = st.text_input("Password (min 6 chars)", type="password", key="su_pwd")
                ok = st.form_submit_button("Create account", width="stretch")
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


def main_app() -> None:
    user = st.session_state["user"]
    with st.sidebar:
        st.markdown("## 🔥 GymCoach<span style='color:#E11D2E'>AI</span>", unsafe_allow_html=True)
        page = st.radio("Navigate", PAGES, label_visibility="collapsed")
        st.divider()
        if st.button("Log out", width="stretch"):
            db.sign_out()
            st.rerun()

    st.title(page)
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


try:
    db.get_client()
except RuntimeError as err:
    st.error(str(err))
    st.stop()

db.init_cookies()          # cookie component: must run on every script run
db.restore_session()       # after a browser refresh, log back in from the cookie
if "user" not in st.session_state:
    db.wait_for_cookies()  # first load: let the cookie arrive before showing login
    auth_screen()
else:
    db.sync_cookie()       # keep the cookie in step with the rotating refresh token
    main_app()