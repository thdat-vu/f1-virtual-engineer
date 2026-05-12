-- 0003_radio_history.sql
-- Persistence for /radio/analyze classifications per signed-in user (issue #95).
-- Apply once via the Supabase SQL editor; this repo does not run automated migrations.
--
-- Backend writes use the service-role key, which bypasses RLS, so the
-- application is responsible for setting user_id from the verified JWT
-- `sub` claim. Never trust client-supplied user ids. The RLS policies
-- below cover any non-service-role access (e.g. direct PostgREST reads
-- from the browser using the user's own JWT).

create table if not exists public.radio_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  transcript text not null,
  driver text,
  classification text not null,
  severity text not null,
  trigger_phrase text,
  fallback boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists radio_history_user_id_created_at_idx
  on public.radio_history (user_id, created_at desc);

create index if not exists radio_history_user_driver_idx
  on public.radio_history (user_id, driver);

alter table public.radio_history enable row level security;

drop policy if exists "owner can select" on public.radio_history;
create policy "owner can select" on public.radio_history
  for select using (auth.uid() = user_id);

drop policy if exists "owner can insert" on public.radio_history;
create policy "owner can insert" on public.radio_history
  for insert with check (auth.uid() = user_id);
