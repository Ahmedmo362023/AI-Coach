-- Step 4: medical report RAG (pgvector inside Supabase, protected by RLS).
-- Run once in the Supabase SQL Editor. Safe to run again.

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
