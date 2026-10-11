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
# st.session_state is wiped on refresh, so Supabase's refresh token lives in a browser
# cookie. Hosts like Streamlit Cloud strip cookies before they reach the server, so the
# server cannot read them; a tiny bundled component (utils/cookie_component) reads and
# writes document.cookie in the browser and reports the value back to Python.
import os as _os

import streamlit.components.v1 as _components

_cookie_component = _components.declare_component(
    "gc_cookies", path=_os.path.join(_os.path.dirname(__file__), "cookie_component")
)


def init_cookies() -> None:
    """Call once at the top of EVERY run (same place each time), before restore_session()."""
    cmd = st.session_state.get("_cookie_cmd") or {}
    val = _cookie_component(
        name=COOKIE_NAME, op=cmd.get("op"), token=cmd.get("token"), days=COOKIE_DAYS,
        key="gc_cookie_cmp", default=None,
    )
    if val is not None:
        st.session_state["_cookie_val"] = val  # None until the browser has answered


def _queue(op: str, token: str | None = None) -> None:
    """Tell the browser to set/clear the cookie. Re-sent every run, so it is never lost."""
    st.session_state["_cookie_cmd"] = {"op": op, "token": token}


def _read_cookie() -> str | None:
    try:  # works when the host forwards cookies (local runs)
        t = st.context.cookies.get(COOKIE_NAME)
        if isinstance(t, str) and t:
            return t
    except Exception:  # noqa: BLE001
        pass
    raw = (st.session_state.get("_cookie_val") or {}).get("cookies", "")
    for part in raw.split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE_NAME and v:
            from urllib.parse import unquote

            return unquote(v)
    return None


def _write_cookie(token: str) -> None:
    _queue("set", token)
    st.session_state["_cookie_token"] = token


def _clear_cookie() -> None:
    st.session_state.pop("_cookie_token", None)
    st.session_state["_cookie_clear"] = True  # a stale cookie must not log us straight back in
    _queue("clear")


def restore_session() -> bool:
    """After a refresh, log the user back in from the cookie. True if logged in."""
    if "user" in st.session_state:
        return True
    if st.session_state.get("_cookie_clear"):
        return False
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
        _queue("clear")
        return False


def wait_for_cookies() -> None:
    """Call on the signed-out path. On a fresh page load the browser has not reported its
    cookies yet; show nothing (instead of flashing the login form) until it does. The
    component's answer triggers the next run by itself."""
    if st.session_state.get("_cookie_val") is None and not st.session_state.get("_cookie_clear"):
        st.markdown("<p style='color:#8a8a8a;padding:2rem'>Loading…</p>", unsafe_allow_html=True)
        st.stop()


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
    if token != st.session_state.get("_cookie_token"):
        _write_cookie(token)
        st.rerun()  # the command is delivered by the component call at the top of the next run


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