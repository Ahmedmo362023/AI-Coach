"""Supabase client + auth helpers."""
import os

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
# st.session_state is wiped on refresh, so we keep Supabase's refresh token in a browser
# cookie. READING is synchronous: the browser sends its cookies with the page request and
# Streamlit exposes them as st.context.cookies, so the very first run already knows the
# token (no "component answers one rerun late" race). WRITING needs JavaScript, done by a
# tiny zero-height HTML snippet that sets document.cookie.


def init_cookies() -> None:
    """Kept for compatibility: nothing to set up any more."""


def _read_cookie() -> str | None:
    try:
        return st.context.cookies.get(COOKIE_NAME) or None
    except Exception:  # noqa: BLE001
        return None


def _cookie_js(token: str | None) -> None:
    """Set (or, with None, delete) the cookie in the browser."""
    import json

    import streamlit.components.v1 as components

    if token:
        age = COOKIE_DAYS * 86400
        body = f"var v={json.dumps(token)};c=n+'='+encodeURIComponent(v)+'; max-age={age}'+base;"
    else:
        body = "c=n+'=; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT'+base;"
    components.html(
        "<script>(function(){var n=%s;var base='; path=/; SameSite=Lax'+"
        "(location.protocol==='https:'?'; Secure':'');var c;%s document.cookie=c;})();</script>"
        % (json.dumps(COOKIE_NAME), body),
        height=0,
    )


def _write_cookie(token: str) -> None:
    _cookie_js(token)
    st.session_state["_cookie_token"] = token


def _clear_cookie() -> None:
    st.session_state.pop("_cookie_token", None)
    st.session_state["_cookie_clear"] = True  # the delete snippet is rendered by wait_for_cookies()


def restore_session() -> bool:
    """After a refresh, log the user back in from the cookie. True if logged in."""
    if "user" in st.session_state:
        return True
    if st.session_state.get("_cookie_clear"):
        return False  # just logged out: the browser's old cookie must not log us back in
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
        _cookie_js(None)
        return False


def wait_for_cookies() -> None:
    """Call on the signed-out screen. Cookies are read synchronously, so nothing to wait for;
    after a log out it deletes the browser cookie (a rerun right after the click would
    otherwise drop the snippet before the browser ran it)."""
    if st.session_state.get("_cookie_clear"):
        _cookie_js(None)


def sync_cookie() -> None:
    """Keep the cookie equal to the client's current refresh token (it rotates)."""
    if "user" not in st.session_state:
        return
    try:
        session = get_client().auth.get_session()
    except Exception:  # noqa: BLE001
        return
    token = session.refresh_token if session else None
    if not token:
        return
    st.session_state.pop("_cookie_clear", None)
    # Render the snippet on EVERY run while logged in. Its content only changes when the
    # token changes, so the browser runs it once per token; and if a run was interrupted
    # before the snippet loaded, the next run puts it back, so the write is never lost.
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