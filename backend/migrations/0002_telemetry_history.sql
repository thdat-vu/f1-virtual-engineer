-- 0002_telemetry_history.sql
-- Persistence for /telemetry lookups per signed-in user (issue #94).
-- Mirrors 0001_analyze_history.sql: idempotent, RLS-scoped by auth.uid().
--
-- Backend writes go through the service-role key (RLS bypass), so the
-- application is responsible for stamping user_id from the verified JWT
-- `sub` claim. The RLS policies below cover any non-service-role access.

create table if not exists public.telemetry_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  year int not null,
  event text not null,
  session_type text not null,
  driver text not null,
  lap_number int,
  created_at timestamptz not null default now()
);

create index if not exists telemetry_history_user_id_created_at_idx
  on public.telemetry_history (user_id, created_at desc);

alter table public.telemetry_history enable row level security;

drop policy if exists "owner can select" on public.telemetry_history;
create policy "owner can select" on public.telemetry_history
  for select using (auth.uid() = user_id);

drop policy if exists "owner can insert" on public.telemetry_history;
create policy "owner can insert" on public.telemetry_history
  for insert with check (auth.uid() = user_id);
