-- Step 3: add meal type (breakfast/lunch/...) to the meals table.
-- Run once in the Supabase SQL Editor. Safe to run again.
alter table public.meals add column if not exists meal_type text;

alter table public.meals drop constraint if exists meals_meal_type_check;
alter table public.meals add constraint meals_meal_type_check
  check (meal_type is null or meal_type in ('breakfast','lunch','dinner','snack','other'));
