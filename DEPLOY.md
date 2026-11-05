# Deploying GymCoachAI on Streamlit Community Cloud

## 1. Database (once)
Supabase SQL Editor: run `db/schema.sql`, then `db/migrations/004_profile_sex.sql`.

## 2. Push to GitHub
`.env` and `.streamlit/secrets.toml` are git-ignored. Check on GitHub that neither is in the repo.
```
git init && git add . && git commit -m "Initial commit"
git branch -M main && git remote add origin <your-repo-url> && git push -u origin main
```

## 3. Create the app
share.streamlit.io -> Create app -> pick the repo, branch `main`, main file `app.py`.
Advanced settings -> Python 3.12, and paste the contents of `.streamlit/secrets.toml.example`
(with your real values) into **Secrets**.

## 4. Supabase auth URLs
Authentication -> URL Configuration: set **Site URL** to `https://<your-app>.streamlit.app`
and add it under **Redirect URLs**. For quick tests, turn off "Confirm email" (Providers -> Email).

## 5. Smoke test
Sign up, save a profile, log a workout and a meal, save a short report, generate the weekly report.

## Notes
- Use the anon/publishable Supabase key only, never service_role.
- Free apps go to sleep when idle (wake with one click); free Supabase projects pause after inactivity.
- Reports are sent to Google's Gemini API; mention that in a privacy notice.
- A `Dockerfile` is included for other hosts (Render, Railway, Fly.io); Streamlit Community Cloud ignores it.
- Not medical advice.
