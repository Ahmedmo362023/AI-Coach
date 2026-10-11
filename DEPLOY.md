# Deploying GymCoachAI (Streamlit Community Cloud + Supabase)

## 1. Database (once)
In the Supabase SQL Editor run `db/schema.sql` on a fresh project.
On an older project run only the migrations you are missing:
`002_meals_meal_type.sql`, `003_report_rag.sql`.

## 2. Push to GitHub
`.env` and `.streamlit/secrets.toml` are git-ignored: never commit keys.
```
git init && git add . && git commit -m "GymCoachAI"
git branch -M main && git remote add origin <your-repo-url> && git push -u origin main
```
Check on GitHub that no `.env` file is in the repo.

## 3. Create the app
share.streamlit.io -> New app -> pick the repo, branch `main`, main file `app.py`.
Advanced settings -> Python 3.12 (3.11 also works) and paste the keys from
`.streamlit/secrets.toml.example` into **Secrets**.

## 4. Tell Supabase where the app lives
Authentication -> URL Configuration:
- **Site URL** = your `https://<app>.streamlit.app` address (otherwise confirmation
  emails point to localhost).
- Add the same address under **Redirect URLs**.
For quick tests you can turn off "Confirm email" under Authentication -> Providers -> Email.

## 5. Smoke test on the live app
1. Sign up and log in. 2. Save a profile. 3. Log a workout and a meal.
4. Paste a short report and save it. 5. Generate the weekly report.

## Notes
- Use the **anon / publishable** Supabase key only. Never put the service_role key in the app:
  row-level security is what keeps users' data apart.
- Reports are sent to Google's Gemini API for embedding and answers. The upload tab asks for consent;
  say so in your privacy notice if other people will use the app.
- Free tiers have quotas, and free Supabase projects can pause after a period of inactivity.
  If the app suddenly fails to connect, check the Supabase dashboard first.
- If a Gemini model is retired, set `GEMINI_MODEL` in Secrets, no code change needed.
- Not medical advice.
