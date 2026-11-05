# GymCoachAI 

[![CI](https://github.com/Ahmedmo362023/AI-Coach/actions/workflows/ci.yml/badge.svg)](https://github.com/Ahmedmo362023/AI-Coach/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-app-FF4B4B)

A gym tracker and AI coach that **computes every number in code** and uses an LLM only to **interpret** them.
Log workouts and meals in plain Egyptian Arabic or English, upload a medical report, and get plans and
weekly reports that take it into account.

<!-- Live demo: add your app URL here, e.g. **Live demo:** https://your-app.streamlit.app -->
<!-- Screenshots: add docs/dashboard.png and docs/coach.png, then uncomment:
![Dashboard](docs/dashboard.png)
-->

## Features

| Page | What it does |
|------|--------------|
| **Dashboard** | Weekly training volume, daily calories (14 days), weight trend, per-exercise progress charts, streaks, achievements and daily calorie/protein targets. |
| **Workout Log** | Write a session the way you'd tell a friend (`3 sets سحب عالي 40 كيلو`); Gemini turns it into structured sets you review before saving. Repeat a past workout, browse history, delete entries. |
| **Nutrition** | Describe what you ate; get per-item calorie and macro estimates (Egyptian foods included), edit them, then save to a daily log. |
| **Medical Report** | Upload a PDF/TXT report (consent required). It is chunked, embedded and indexed. Ask questions about it, or build a weekly plan that respects what it says. |
| **AI Coach** | Chat with a coach that sees your real numbers, plus a weekly report (Arabic or English) with concrete next-week actions. |

## How it works

```
Browser ── Streamlit (Python) ──┬── Supabase: Auth · Postgres · pgvector · Row Level Security
                                └── Gemini API: parsing · embeddings · coaching text
```

1. **Parsing**: free text goes to Gemini with a strict JSON schema; the app validates and lets the user fix rows before anything is saved.
2. **Analytics** (`utils/analytics.py`, `utils/progress.py`): weekly volume, estimated 1RM (Epley), PR detection, streaks, calorie targets and rule-based flags are plain Python functions.
3. **RAG** (`utils/rag.py`): report text is cleaned, split into overlapping chunks, embedded with `gemini-embedding-001` (768 dims) and stored in pgvector. Retrieval runs as the logged-in user, so RLS applies.
4. **Coaching** (`utils/llm.py`, `utils/chat.py`): the model receives the computed metrics plus retrieved excerpts and only explains them.

## Design decisions

- **Numbers in code, words from the LLM.** Metrics are deterministic and unit-tested; the prompts forbid the model from recomputing or inventing numbers.
- **Untrusted text is data.** Report excerpts and chat messages are treated as untrusted input; prompts tell the model not to follow instructions found in them.
- **Per-user isolation.** RLS on every table, `SECURITY INVOKER` search function, and one Supabase client per browser session (never a shared cached client).
- **Safety rails.** The coach does not diagnose or touch medication, cites report excerpts, and sends users to a doctor for risky conditions.
- **Cost control.** Chat input is length-limited and rate-limited; the report search only runs when a question looks medical.

## Project structure

```
app.py              entry point: auth + navigation
ui/                 one module per page (dashboard, workout, nutrition, medical, coach)
utils/              framework-free logic: analytics, progress, rag, llm, chat, meals, workouts
db/                 schema.sql and migrations
tests/              51 pytest tests (no network or API keys needed)
Dockerfile          container image for non-Streamlit-Cloud hosts
```

## Run locally

1. Create a Supabase project. In the SQL Editor run `db/schema.sql`, then `db/migrations/004_profile_sex.sql`.
2. `cp .env.example .env` and fill in `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `GEMINI_API_KEY`.
3. `pip install -r requirements.txt`
4. `streamlit run app.py`

With Docker: `docker build -t gymcoach . && docker run --env-file .env -p 8501:8501 gymcoach`

## Tests

```
pip install pytest reportlab
python -m pytest tests
```

## Deploy

See [DEPLOY.md](DEPLOY.md) (Streamlit Community Cloud + Supabase).

## Known limitations

- The chat rate limit is kept per browser session, so it is a courtesy limit, not abuse protection.
- Nutrition values are AI estimates; the app asks you to review them before saving.
- Free Streamlit and Supabase tiers sleep or pause when idle.

> Not medical advice. Plans adapt to your report but never replace a doctor.
