# GymCoachAI 🔥

![CI](https://github.com/<your-user>/<your-repo>/actions/workflows/ci.yml/badge.svg)

A gym tracker and AI coach that **computes every number in code** and uses an LLM only to
**interpret** them. Log workouts and meals in plain Egyptian Arabic or English, upload a medical
report, and get plans and weekly reports that respect it.

<!-- Add a screenshot or GIF here: docs/demo.gif -->
**Live demo:** _add your URL_

## Features
- **Plain-language logging**: "3 sets سحب عالي 40 kg" becomes structured sets (Gemini → validated JSON).
- **Nutrition tracker**: Egyptian-food-aware calorie/macro estimates, reviewed by the user before saving.
- **Analytics engine**: weekly volume, estimated 1RM, PR detection, streaks, daily calorie/protein targets, rule-based flags.
- **Medical-aware plans (RAG)**: report text is chunked, embedded (`gemini-embedding-001`, 768 dims) and stored in Postgres with pgvector.
- **AI coach**: weekly report and chat, grounded in the user's own data, with citations to report excerpts.
- **Privacy by design**: row-level security on every table; retrieval runs as the logged-in user (`SECURITY INVOKER`).

## Design decisions
- **Numbers in code, words from the LLM.** Metrics are deterministic and unit-tested; the model never computes or invents them.
- **Untrusted text is data.** Report excerpts and chat messages are treated as untrusted; prompts forbid following instructions inside them.
- **No shared auth state.** One Supabase client per browser session; no cached client carries a user's JWT to another user.
- **Safety rails.** The coach never diagnoses or changes medication, and sends users to a doctor for risky conditions.

## Architecture
```
Browser ── Streamlit (Python) ──┬── Supabase: Auth · Postgres · pgvector · RLS
                                └── Gemini API: structuring · embeddings · coaching
```

## Stack
Streamlit · Supabase · pgvector · Gemini · pandas · Plotly · pytest · Docker · GitHub Actions

## Run locally
1. Create a Supabase project; in the SQL Editor run `db/schema.sql`, then `db/migrations/004_profile_sex.sql`.
2. `cp .env.example .env` and fill in the keys.
3. `pip install -r requirements.txt`
4. `streamlit run app.py`

Or with Docker: `docker build -t gymcoach . && docker run --env-file .env -p 8501:8501 gymcoach`

## Tests
`pip install pytest reportlab` then `python -m pytest tests` (51 tests, no network or keys needed).

## Deploy
See [DEPLOY.md](DEPLOY.md) (Streamlit Community Cloud + Supabase). A Dockerfile is included for other hosts.

> Not medical advice. Plans adapt to your report but never replace a doctor.
