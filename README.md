# GymCoachAI 🔥

Gym tracker + training/nutrition planner with an AI coach.
Numbers are computed in code; the LLM (Gemini) only interprets them.
Medical report text is chunked, embedded (gemini-embedding-001, 768 dims) and stored in Supabase pgvector behind row-level security, so plans adapt to it.

## Stack
Streamlit · Supabase (auth + Postgres + pgvector) · Gemini

## Setup
1. Create a Supabase project and run `db/schema.sql` in the SQL Editor (already includes everything up to Step 4).
2. `cp .env.example .env` and fill in the keys.
3. `pip install -r requirements.txt`
4. `streamlit run app.py`

## Deploy
See [DEPLOY.md](DEPLOY.md) (Streamlit Community Cloud + Supabase, step by step).

## Tests
`pip install pytest reportlab` then `python -m pytest tests` (no network or keys needed).

## Roadmap
- [x] Step 1: scaffold, red/black theme, auth, DB schema
- [x] Step 2: workout logging (plain-language → structured sets)
- [x] Step 3: nutrition tracker (run `db/migrations/002_meals_meal_type.sql` once if you created the DB before this step)
- [x] Step 4: medical report RAG (run `db/migrations/003_report_rag.sql` once if your DB predates this step)
- [x] Step 5: analytics engine (weekly metrics, PRs, flags, charts) + AI coach report
- [x] Step 6: deployment guide (DEPLOY.md, secrets template, .gitignore)

> Not medical advice. Plans adapt to your report but never replace a doctor.
