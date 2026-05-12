-- Apply once via the Supabase SQL editor.
-- Persists radio classifications per signed-in user (#95).

create table public.radio_history (
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

create index radio_history_user_id_created_at_idx
  on public.radio_history (user_id, created_at desc);

create index radio_history_user_driver_idx
  on public.radio_history (user_id, driver);

alter table public.radio_history enable row level security;

create policy "owner can select" on public.radio_history
  for select using (auth.uid() = user_id);

create policy "owner can insert" on public.radio_history
  for insert with check (auth.uid() = user_id);
