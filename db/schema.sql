-- GymCoachAI schema for Supabase (run in SQL Editor)

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  age int,
  height_cm numeric,
  weight_kg numeric,
  goal text check (goal in ('fat_loss','muscle_gain','strength','general_fitness')),
  experience text check (experience in ('beginner','intermediate','advanced')),
  days_per_week int,
  created_at timestamptz default now()
);

create table if not exists public.workouts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  performed_on date not null default current_date,
  title text,
  raw_text text,            -- what the user typed in plain language
  notes text,
  created_at timestamptz default now()
);

create table if not exists public.workout_sets (
  id uuid primary key default gen_random_uuid(),
  workout_id uuid not null references public.workouts(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  exercise text not null,
  muscle_group text,
  set_number int not null,
  reps int not null,
  weight_kg numeric,
  rpe numeric,
  created_at timestamptz default now()
);

create table if not exists public.meals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  eaten_on date not null default current_date,
  meal_type text check (meal_type is null or meal_type in ('breakfast','lunch','dinner','snack','other')),
  name text not null,
  calories numeric,
  protein_g numeric,
  carbs_g numeric,
  fat_g numeric,
  created_at timestamptz default now()
);

create table if not exists public.body_metrics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  measured_on date not null default current_date,
  weight_kg numeric,
  body_fat_pct numeric,
  notes text
);

create table if not exists public.medical_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text,
  content text not null,    -- extracted text of the report (no images)
  created_at timestamptz default now()
);

create table if not exists public.coach_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  period_start date,
  period_end date,
  metrics jsonb,            -- numbers computed in code
  report_text text,         -- LLM interpretation of those numbers
  created_at timestamptz default now()
);

-- Row Level Security: each user sees only their own rows
do $$
declare t text;
begin
  foreach t in array array['workouts','workout_sets','meals','body_metrics','medical_reports','coach_reports']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "own rows" on public.%I', t);
    execute format(
      'create policy "own rows" on public.%I for all using (auth.uid() = user_id) with check (auth.uid() = user_id)', t);
  end loop;
end $$;

alter table public.profiles enable row level security;
drop policy if exists "own profile" on public.profiles;
create policy "own profile" on public.profiles
  for all using (auth.uid() = id) with check (auth.uid() = id);

-- Auto-create a profile on signup
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, new.raw_user_meta_data->>'full_name')
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ===== Step 4: report RAG =====

create extension if not exists vector with schema extensions;

create table if not exists public.report_chunks (
  id uuid primary key default gen_random_uuid(),
  report_id uuid not null references public.medical_reports(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  embedding extensions.vector(768) not null,
  created_at timestamptz default now()
);

create index if not exists report_chunks_report_idx on public.report_chunks (report_id);
create index if not exists report_chunks_embedding_idx
  on public.report_chunks using hnsw (embedding extensions.vector_cosine_ops);

-- Each user sees only their own chunks
alter table public.report_chunks enable row level security;
drop policy if exists "own rows" on public.report_chunks;
create policy "own rows" on public.report_chunks
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Similarity search. SECURITY INVOKER: runs as the logged-in user, so RLS applies
-- and nobody can ever retrieve another user's report text.
create or replace function public.match_report_chunks(
  query_embedding extensions.vector(768),
  match_count int default 5,
  p_report_id uuid default null
)
returns table (id uuid, report_id uuid, chunk_index int, content text, similarity float)
language sql stable security invoker
set search_path = public, extensions
as $$
  select c.id, c.report_id, c.chunk_index, c.content,
         (1 - (c.embedding <=> query_embedding))::float as similarity
  from public.report_chunks c
  where p_report_id is null or c.report_id = p_report_id
  order by c.embedding <=> query_embedding
  limit least(greatest(match_count, 1), 20);
$$;
