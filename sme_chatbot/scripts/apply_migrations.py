"""Apply the SQL schema to DATABASE_URL.

Idempotent: every statement in migrations/001_initial.sql uses
``IF NOT EXISTS``, so this can run safely on every boot. Invoked from the
container's start.sh for the web role.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def main() -> int:
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set; skipping migrations.")
        return 0

    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print(f"No .sql files found in {_MIGRATIONS_DIR}")
        return 0

    # Render's connection strings work with sslmode=require.
    connect_kwargs = {"connect_timeout": 30}
    if "sslmode=" not in url:
        connect_kwargs["sslmode"] = "require"

    with psycopg.connect(url, **connect_kwargs) as conn:
        for f in files:
            print(f"[migrate] applying {f.name} ...")
            with conn.cursor() as cur:
                cur.execute(f.read_text())
            conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"
            )
            n = cur.fetchone()[0]
    print(f"[migrate] done. {n} tables present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
