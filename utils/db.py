"""Supabase client + auth helpers."""
import os

import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


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


def sign_up(email: str, password: str, full_name: str = ""):
    return get_client().auth.sign_up(
        {"email": email, "password": password, "options": {"data": {"full_name": full_name}}}
    )


def sign_in(email: str, password: str):
    return get_client().auth.sign_in_with_password({"email": email, "password": password})


def sign_out() -> None:
    try:
        get_client().auth.sign_out()
    finally:
        for k in list(st.session_state.keys()):
            if k in ("user", "session", "sb_client") or str(k).startswith(("wk_", "ml_", "mr_")):
                st.session_state.pop(k, None)
