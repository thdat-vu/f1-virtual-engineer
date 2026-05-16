-- 0005_rationale_async.sql
-- Adds the column the async rationale worker writes back into (#139 PR3).
-- Apply once via the Supabase SQL editor; this repo doesn't run automated
-- migrations.
--
-- Backfilled rows look like:
--   rationale_source = 'template'  ->  inserted synchronously by /analyze
--   rationale_source = 'llm'       ->  rationale_text populated by worker
--
-- The worker is idempotent on rationale_source: if it sees 'llm' on a row
-- it tried to update, it silently skips. So a re-delivered task can't
-- double-write.

alter table public.analyze_history
  add column if not exists rationale_text text;
