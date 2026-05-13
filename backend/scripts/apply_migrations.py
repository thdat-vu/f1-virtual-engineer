"""Apply SQL migrations from backend/migrations/ to a Supabase Postgres.

Usage:
    cd backend
    python3 scripts/apply_migrations.py            # run all migrations
    python3 scripts/apply_migrations.py 0001       # run a single file by prefix

Reads ``SUPABASE_DB_URL`` from ``backend/.env`` (or the environment).
Use the **Session pooler** connection string from Supabase dashboard
(Project Settings → Database → Session pooler URI), with your DB
password substituted in for ``[YOUR-PASSWORD]``.

Each migration is run in a single transaction; if anything in the file
errors, the whole file is rolled back. Already-applied migrations are
safe to re-run because every statement uses ``if not exists`` /
``drop policy if exists`` guards.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Explicit path to backend/.env so this script works whether you run it
    # from backend/ (as the docstring suggests) or from the repo root.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

try:
    import psycopg
except ImportError:
    sys.stderr.write(
        "psycopg is required. Install it with:\n"
        "    python3 -m pip install 'psycopg[binary]'\n"
    )
    sys.exit(1)


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _select_migrations(prefix: str | None) -> list[Path]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if prefix:
        files = [f for f in files if f.stem.startswith(prefix)]
    if not files:
        raise SystemExit(f"No migrations matched prefix={prefix!r} in {MIGRATIONS_DIR}")
    return files


def main() -> None:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url or "[YOUR-PASSWORD]" in db_url:
        raise SystemExit(
            "SUPABASE_DB_URL is not set or still contains a [YOUR-PASSWORD] placeholder.\n"
            "Add it to backend/.env, e.g.:\n"
            "    SUPABASE_DB_URL=postgresql://postgres.<ref>:<password>@<pooler-host>:5432/postgres"
        )

    prefix = sys.argv[1] if len(sys.argv) > 1 else None
    files = _select_migrations(prefix)

    print(f"Applying {len(files)} migration(s) to Supabase…")
    with psycopg.connect(db_url, autocommit=False) as conn:
        for path in files:
            sql = path.read_text(encoding="utf-8")
            print(f"  → {path.name}")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()
