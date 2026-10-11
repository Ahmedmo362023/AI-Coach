-- Step 7: optional "sex" on the profile, used only to make the daily calorie estimate more accurate.
-- Run once in the Supabase SQL Editor. Safe to run twice.
alter table public.profiles
  add column if not exists sex text check (sex is null or sex in ('male', 'female'));