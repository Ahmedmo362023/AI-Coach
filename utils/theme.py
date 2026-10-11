"""GymCoachAI theme: black + red.

Public API (used by app.py and the pages): RED, inject_theme(), card().
"""
from html import escape

import streamlit as st

RED = "#E11D2E"
RED_DARK = "#B3121F"
BLACK = "#0A0A0A"
SURFACE = "#141414"
SURFACE_2 = "#1C1C1C"
BORDER = "#2A2A2A"
TEXT = "#F5F5F5"
MUTED = "#9A9A9A"

_ROOT = (
    ":root{"
    f"--red:{RED};--red-dark:{RED_DARK};--black:{BLACK};--surface:{SURFACE};"
    f"--surface-2:{SURFACE_2};--border:{BORDER};--text:{TEXT};--muted:{MUTED};"
    "}"
)

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, button, input, textarea {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
h1, h2, h3, h4, .gc-hero { font-family: 'Poppins', 'Inter', sans-serif; }

/* Arabic/English paragraphs pick their own direction */
.stMarkdown p, .stMarkdown li { unicode-bidi: plaintext; text-align: start; }

/* ---------- App background ---------- */
.stApp {
  background:
    radial-gradient(900px 420px at 88% -8%, rgba(225,29,46,.20), transparent 62%),
    radial-gradient(700px 380px at -5% 105%, rgba(225,29,46,.10), transparent 60%),
    var(--black);
  color: var(--text);
}
[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer, [data-testid="stDeployButton"] { visibility: hidden; }
.block-container { padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1200px; }

/* ---------- Typography ---------- */
h1, h2, h3, h4 { color: var(--text); letter-spacing: -0.02em; }
h1 { font-weight: 800; }
h4 { font-weight: 700; margin-top: 1.4rem; }
h4::before {
  content: ""; display: inline-block; width: 4px; height: 1em; margin-right: .55rem;
  background: var(--red); border-radius: 2px; vertical-align: -0.12em;
}
[data-testid="stSidebar"] h2::before { display: none; }
[data-testid="stCaptionContainer"], .gc-muted { color: var(--muted); }
hr { border-color: var(--border) !important; }
a { color: var(--red); }

/* ---------- Hero + cards ---------- */
.gc-hero {
  font-size: clamp(2.4rem, 5vw, 3.7rem); font-weight: 800; line-height: 1.04;
  letter-spacing: -0.035em; color: var(--text);
}
.gc-hero span { color: var(--red); text-shadow: 0 0 34px rgba(225,29,46,.55); }
.gc-card {
  position: relative; background: linear-gradient(145deg, var(--surface-2), var(--surface));
  border: 1px solid var(--border); border-left: 3px solid var(--red);
  border-radius: 14px; padding: 1rem 1.2rem; margin-top: .85rem;
  transition: transform .15s ease, border-color .15s ease, box-shadow .15s ease;
}
.gc-card:hover {
  transform: translateY(-2px); border-color: var(--red);
  box-shadow: 0 8px 28px rgba(225,29,46,.18);
}
.gc-card h4 { margin: 0 0 .25rem 0; font-size: 1.05rem; }
.gc-card h4::before { display: none; }
.gc-card p { margin: 0; color: var(--muted); font-size: .92rem; line-height: 1.5; }
.gc-tag {
  position: absolute; top: .9rem; right: 1rem; font-size: .68rem; font-weight: 700;
  letter-spacing: .08em; text-transform: uppercase; color: var(--red);
  background: rgba(225,29,46,.12); border: 1px solid rgba(225,29,46,.4);
  padding: .15rem .55rem; border-radius: 999px;
}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
  background: #0D0D0D; border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] [role="radiogroup"] { gap: .25rem; }
[data-testid="stSidebar"] [role="radiogroup"] label {
  padding: .55rem .8rem; border-radius: 10px; border-left: 3px solid transparent;
  transition: background .12s ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: rgba(255,255,255,.04); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: rgba(225,29,46,.14); border-left-color: var(--red);
}

/* ---------- Buttons ---------- */
.stButton > button, [data-testid="stFormSubmitButton"] > button, .stDownloadButton > button {
  border-radius: 10px; font-weight: 600; padding: .5rem 1.1rem;
  background: var(--surface-2); color: var(--text); border: 1px solid var(--border);
  transition: all .15s ease;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  border-color: var(--red); color: #fff; box-shadow: 0 0 0 1px var(--red) inset;
}
button[kind="primary"], button[kind="primaryFormSubmit"] {
  background: linear-gradient(135deg, var(--red), var(--red-dark)) !important;
  border: none !important; color: #fff !important;
  box-shadow: 0 6px 20px rgba(225,29,46,.35);
}
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {
  filter: brightness(1.12); box-shadow: 0 8px 26px rgba(225,29,46,.5) !important;
}
button:disabled { opacity: .45 !important; box-shadow: none !important; }

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] { gap: .4rem; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] {
  background: transparent; color: var(--muted); font-weight: 600; padding: .6rem 1rem;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text); }
.stTabs [aria-selected="true"] { color: #fff !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--red) !important; height: 3px; }

/* ---------- Inputs ---------- */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
  background: var(--surface) !important; border-radius: 10px !important;
  border: 1px solid var(--border) !important;
}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within,
[data-baseweb="select"] > div:focus-within {
  border-color: var(--red) !important; box-shadow: 0 0 0 3px rgba(225,29,46,.22) !important;
}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea { color: var(--text); }
label, [data-testid="stWidgetLabel"] p { color: #CFCFCF; font-weight: 500; }
[data-testid="stForm"] {
  background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
  padding: 1.2rem 1.3rem;
}
[data-testid="stFileUploaderDropzone"] {
  background: var(--surface); border: 1px dashed #3A3A3A; border-radius: 12px;
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--red); }

/* ---------- Metrics ---------- */
[data-testid="stMetric"] {
  background: linear-gradient(145deg, var(--surface-2), var(--surface));
  border: 1px solid var(--border); border-radius: 14px; padding: .9rem 1.1rem;
}
[data-testid="stMetricLabel"] p {
  color: var(--muted); text-transform: uppercase; letter-spacing: .06em;
  font-size: .72rem; font-weight: 600;
}
[data-testid="stMetricValue"] { font-weight: 800; color: var(--text); }

/* ---------- Expanders, alerts, misc ---------- */
[data-testid="stExpander"] details {
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
}
[data-testid="stExpander"] summary:hover { color: var(--red); }
[data-testid="stAlert"] {
  background: var(--surface); border: 1px solid var(--border);
  border-left: 3px solid var(--red); border-radius: 12px; color: var(--text);
}
[data-testid="stToast"] { background: var(--surface-2); border: 1px solid var(--red); }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
  border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
}
[data-testid="stSlider"] [role="slider"] { background: var(--red); }
code { color: #FF8A94; background: var(--surface-2); }

/* ---------- Achievements ---------- */
.gc-ach-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: .75rem; margin-top: .6rem;
}
.gc-ach {
  display: flex; gap: .85rem; align-items: center; padding: .8rem 1rem; border-radius: 14px;
  background: linear-gradient(145deg, rgba(225,29,46,.18), var(--surface));
  border: 1px solid rgba(225,29,46,.55);
}
.gc-ach.locked {
  background: var(--surface); border: 1px dashed var(--border); opacity: .6; filter: grayscale(1);
}
.gc-ach-icon { font-size: 1.7rem; line-height: 1; }
.gc-ach-title { font-weight: 700; font-size: .95rem; color: var(--text); }
.gc-ach-desc { color: var(--muted); font-size: .8rem; line-height: 1.35; }
.gc-ach-prog { color: var(--red); font-size: .74rem; font-weight: 700; margin-top: .2rem; }
.gc-ach.locked .gc-ach-prog { color: var(--muted); }

/* ---------- Scrollbar ---------- */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: #2E2E2E; border-radius: 8px; }
::-webkit-scrollbar-thumb:hover { background: var(--red); }
"""


def inject_theme() -> None:
    st.markdown(f"<style>{_ROOT}{_CSS}</style>", unsafe_allow_html=True)


def card(title: str, body: str, badge: str | None = None) -> None:
    badge_html = f'<span class="gc-tag">{escape(badge)}</span>' if badge else ""
    st.markdown(
        f'<div class="gc-card">{badge_html}<h4>{escape(title)}</h4><p>{escape(body)}</p></div>',
        unsafe_allow_html=True,
    )