-- 0001_analyze_history.sql
-- Persistence for /analyze queries per signed-in user (issue #93).
-- Apply once via the Supabase SQL editor; this repo does not run automated migrations.
--
-- Backend writes use the service-role key, which bypasses RLS, so the
-- application is responsible for setting user_id from the verified JWT
-- `sub` claim. Never trust client-supplied user ids. The RLS policies
-- below cover any non-service-role access (e.g. direct PostgREST reads
-- from the browser using the user's own JWT).

create table if not exists public.analyze_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  query text not null,
  driver text,
  event text,
  year int,
  session_type text,
  agent_response text not null,
  rationale_source text not null,
  intent_type text,
  created_at timestamptz not null default now()
);

create index if not exists analyze_history_user_id_created_at_idx
  on public.analyze_history (user_id, created_at desc);

alter table public.analyze_history enable row level security;

drop policy if exists "owner can select" on public.analyze_history;
create policy "owner can select" on public.analyze_history
  for select using (auth.uid() = user_id);

drop policy if exists "owner can insert" on public.analyze_history;
create policy "owner can insert" on public.analyze_history
  for insert with check (auth.uid() = user_id);
