-- 0004_saved_queries.sql
-- Persistence for starred /analyze + /telemetry queries (issue #104).
-- Apply once via the Supabase SQL editor; this repo does not run automated migrations.
--
-- Backend writes use the service-role key, which bypasses RLS, so the
-- application is responsible for setting user_id from the verified JWT
-- `sub` claim. Never trust client-supplied user ids. The RLS policies
-- below cover any non-service-role access (e.g. direct PostgREST reads
-- from the browser using the user's own JWT).

create table if not exists public.saved_queries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null check (kind in ('analyze', 'telemetry')),
  payload jsonb not null,
  label text,
  created_at timestamptz not null default now()
);

create index if not exists saved_queries_user_id_created_at_idx
  on public.saved_queries (user_id, created_at desc);

alter table public.saved_queries enable row level security;

drop policy if exists "owner can select" on public.saved_queries;
create policy "owner can select" on public.saved_queries
  for select using (auth.uid() = user_id);

drop policy if exists "owner can insert" on public.saved_queries;
create policy "owner can insert" on public.saved_queries
  for insert with check (auth.uid() = user_id);

drop policy if exists "owner can delete" on public.saved_queries;
create policy "owner can delete" on public.saved_queries
  for delete using (auth.uid() = user_id);
