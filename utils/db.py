"""Supabase client + auth helpers."""
import os
import time
from datetime import datetime, timedelta

import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

# Name and lifetime of the browser cookie that keeps the user logged in across refreshes.
COOKIE_NAME = "gc_rt"
COOKIE_DAYS = 30


def _secret(name: str) -> str | None:
    # Streamlit Cloud uses st.secrets; locally we fall back to .env
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name)


def get_client() -> Client:
    """One Supabase client PER browser session.

    Never cache this with st.cache_resource: the client holds the logged-in
    user's JWT, so a shared client would leak one user's access to others.
    """
    if "sb_client" not in st.session_state:
        url, key = _secret("SUPABASE_URL"), _secret("SUPABASE_ANON_KEY")
        url = (url or "").strip().strip("\"'").rstrip("/")
        key = (key or "").strip().strip("\"'")
        if "YOUR-PROJECT" in url or key == "your-anon-key":
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_ANON_KEY still hold the example values. "
                "Put your real project URL and key in .env, save, and restart Streamlit."
            )
        if not url or not key:
            raise RuntimeError(
                "Missing SUPABASE_URL / SUPABASE_ANON_KEY. "
                "Copy .env.example to .env (or set Streamlit secrets)."
            )
        st.session_state["sb_client"] = create_client(url, key)
    return st.session_state["sb_client"]


# ---------- Stay logged in after a browser refresh ----------
# st.session_state is wiped on refresh, so we keep Supabase's refresh token in a
# cookie and use it to restore the session on the next page load. If the cookie
# library is missing, everything still works; you just log in again after a refresh.


def init_cookies() -> None:
    """Call once at the top of every script run, before restore_session()."""
    try:
        from streamlit_cookies_controller import CookieController

        st.session_state["_cookie_ctl"] = CookieController(key="gc_cookies")
    except Exception:  # noqa: BLE001
        st.session_state.pop("_cookie_ctl", None)


def _read_cookie() -> str | None:
    ctl = st.session_state.get("_cookie_ctl")
    if not ctl:
        return None
    try:
        return ctl.get(COOKIE_NAME)
    except Exception:  # noqa: BLE001  (browser hasn't answered yet: cookies is None)
        return None


def _write_cookie(token: str) -> None:
    ctl = st.session_state.get("_cookie_ctl")
    if not ctl:
        return
    try:
        ctl.set(
            COOKIE_NAME,
            token,
            max_age=COOKIE_DAYS * 86400,
            expires=datetime.now() + timedelta(days=COOKIE_DAYS),
        )
    except Exception:  # noqa: BLE001
        # The library sends the command to the browser first and only then updates its
        # own local copy, which can fail before the browser has answered. Cookie is set.
        pass
    st.session_state["_cookie_token"] = token


def _clear_cookie() -> None:
    ctl = st.session_state.get("_cookie_ctl")
    st.session_state.pop("_cookie_token", None)
    if not ctl:
        return
    try:
        ctl.remove(COOKIE_NAME)
    except Exception:  # noqa: BLE001
        pass


def restore_session() -> bool:
    """After a refresh, log the user back in from the cookie. True if logged in."""
    if "user" in st.session_state:
        return True
    token = _read_cookie()
    if not token:
        return False
    try:
        res = get_client().auth.refresh_session(token)
        if not (res and res.session and res.user):
            raise ValueError("no session")
        st.session_state["user"] = res.user
        return True
    except Exception:  # noqa: BLE001  (expired / revoked token)
        _clear_cookie()
        return False


def wait_for_cookies() -> None:
    """On a fresh page load the cookie component answers one rerun late.

    Pause once so a logged-in user doesn't see the login screen flash.
    """
    if "user" in st.session_state or st.session_state.get("_cookie_wait_done"):
        return
    if not st.session_state.get("_cookie_ctl") or _read_cookie():
        return
    st.session_state["_cookie_wait_done"] = True
    time.sleep(0.6)
    st.rerun()


def sync_cookie() -> None:
    """Keep the cookie equal to the client's current refresh token (it rotates)."""
    if "user" not in st.session_state:
        return
    try:
        session = get_client().auth.get_session()
    except Exception:  # noqa: BLE001
        return
    token = session.refresh_token if session else None
    if token and token != st.session_state.get("_cookie_token"):
        _write_cookie(token)


# ---------- Auth ----------
def sign_up(email: str, password: str, full_name: str = ""):
    return get_client().auth.sign_up(
        {"email": email, "password": password, "options": {"data": {"full_name": full_name}}}
    )


def sign_in(email: str, password: str):
    return get_client().auth.sign_in_with_password({"email": email, "password": password})


def sign_out() -> None:
    _clear_cookie()
    try:
        get_client().auth.sign_out()
    finally:
        for k in list(st.session_state.keys()):
            if k in ("user", "session", "sb_client") or str(k).startswith(("wk_", "ml_", "mr_")):
                st.session_state.pop(k, None)