#!/usr/bin/env python3
"""
Widen encrypted columns from VARCHAR(n) to TEXT.

These columns predate field-level encryption. The models declare them as
EncryptedString, whose impl is Text, but the physical columns were created as
VARCHAR(n) and never altered. Fernet inflates plaintext by roughly 1.4x plus
~57 bytes of overhead, so a value that fits comfortably as plaintext can
overflow the column once encrypted:

    varchar(255) -> INSERT fails above 127 plaintext characters
    varchar(500) -> INSERT fails above 303 plaintext characters

The failure surfaces as a bare 500 ("value too long for type character
varying"), which is why a long document filename or a medication note could
kill a request for no visible reason.

VARCHAR(n) -> TEXT needs no table rewrite in PostgreSQL: both use the same
on-disk representation, so this only drops the length constraint. It is fast
and non-destructive regardless of table size.

Run once on the server:
    sudo -u foodbody bash -c "cd /opt/foodbodyconnection && \
        /opt/foodbodyconnection/venv/bin/python scripts/widen_encrypted_columns.py"

Safe to re-run: columns already TEXT are skipped.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DB_URL") or os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DB_URL not set")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# (table, column) pairs backed by EncryptedString in app/models/table_class.py
TARGETS = [
    ("allergen",           "allergen_name"),
    ("medication",         "medication_name"),
    ("symptom",            "symptom_name"),
    ("symptom",            "symptom_group"),
    ("user_document",      "filename"),
    ("user_document",      "description"),
    ("medication_regimen", "note"),
]


def _dependent_views(conn, tables):
    """Views whose definition references any of these tables.

    PostgreSQL refuses to alter a column a view depends on, so they have to be
    dropped and rebuilt around the change. Definitions are captured first and
    replayed verbatim, inside the same transaction as the ALTERs — if anything
    fails, the views come back untouched along with the original column types.
    """
    rows = conn.execute(text("""
        SELECT DISTINCT v.relname AS view_name,
               pg_get_viewdef(v.oid, true) AS definition
        FROM pg_depend d
        JOIN pg_rewrite r ON r.oid = d.objid
        JOIN pg_class   v ON v.oid = r.ev_class
        JOIN pg_class   s ON s.oid = d.refobjid
        JOIN pg_namespace n ON n.oid = v.relnamespace
        WHERE v.relkind = 'v'
          AND n.nspname = 'public'
          AND s.relname = ANY(:tables)
    """), {"tables": list({t for t, _ in TARGETS})}).fetchall()
    return [(r.view_name, r.definition) for r in rows]


def main() -> None:
    with engine.begin() as conn:
        views = _dependent_views(conn, TARGETS)
        for name, _ in views:
            conn.execute(text(f'DROP VIEW IF EXISTS "{name}"'))

        widened, skipped, missing = [], [], []
        for table, column in TARGETS:
            row = conn.execute(text("""
                SELECT data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :t AND column_name = :c
            """), {"t": table, "c": column}).fetchone()

            if row is None:
                missing.append(f"{table}.{column}")
                continue

            if row.data_type == "text":
                skipped.append(f"{table}.{column}")
                continue

            # Identifiers cannot be bound as parameters; they come from the
            # fixed list above, never from user input.
            conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE TEXT'))
            widened.append(f"{table}.{column} (was {row.data_type}({row.character_maximum_length}))")

        for name, definition in views:
            conn.execute(text(f'CREATE VIEW "{name}" AS {definition}'))

    if views:
        print(f"Rebuilt dependent views ({len(views)}): "
              f"{', '.join(n for n, _ in views)}\n")

    print(f"Widened to TEXT ({len(widened)}):")
    for name in widened:
        print(f"   {name}")
    print(f"\nAlready TEXT ({len(skipped)}):")
    for name in skipped:
        print(f"   {name}")
    if missing:
        print(f"\nNot present in this database ({len(missing)}):")
        for name in missing:
            print(f"   {name}")


if __name__ == "__main__":
    main()
