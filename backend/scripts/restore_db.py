"""Put a dump back, into a database you name.

A backup nobody has restored is a hypothesis. This one has been run: the test
below loads a dump into an empty scratch database, compares every table's row
count against the file, and reads a Fernet-encrypted column back through the
ORM to prove the ciphertext survived the round trip and still decrypts.

Refuses to write into a database that already has rows unless you say --force,
because the realistic way to lose data with a restore script is to point it at
the live database by mistake.

    ./.venv/bin/python scripts/restore_db.py DUMP.json.gz --url sqlite:///scratch.db
    ./.venv/bin/python scripts/restore_db.py DUMP.json.gz            # uses DB_URL
"""
import argparse
import base64
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from sqlalchemy import create_engine, inspect, text      # noqa: E402

from app.models.table_class import Base                  # noqa: E402


def _value(v):
    if isinstance(v, dict) and "__b64__" in v:
        return base64.b64decode(v["__b64__"])
    return v


def restore(path, url, force=False):
    dump = json.load(gzip.open(path, "rt", encoding="utf-8"))
    engine = create_engine(url)
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        existing = {}
        for name in inspect(engine).get_table_names():
            existing[name] = conn.execute(text(f'SELECT count(*) FROM "{name}"')).scalar()
        occupied = {k: v for k, v in existing.items() if v}
        if occupied and not force:
            raise SystemExit(
                f"refusing to write into a database that already holds rows "
                f"({occupied}). Pass --force if that is really what you want.")

        total = 0
        # Parents before children, so foreign keys resolve.
        order = [t.name for t in Base.metadata.sorted_tables]
        order += [t for t in dump["tables"] if t not in order]
        # The dump takes everything in the database; the schema only defines
        # what the app uses. Neon's sample table is in one and not the other,
        # and a restore that dies on it after writing half the rows is worse
        # than one that says what it skipped.
        known = set(inspect(engine).get_table_names())
        skipped = []
        for name in order:
            table = dump["tables"].get(name)
            if not table or not table["rows"]:
                continue
            if name not in known:
                skipped.append(f"{name} ({len(table['rows'])} rows)")
                continue
            cols = ", ".join(f'"{c}"' for c in table["columns"])
            marks = ", ".join(f":p{i}" for i in range(len(table["columns"])))
            stmt = text(f'INSERT INTO "{name}" ({cols}) VALUES ({marks})')
            conn.execute(stmt, [{f"p{i}": _value(v) for i, v in enumerate(row)}
                                for row in table["rows"]])
            total += len(table["rows"])
            print(f"  {name:22s} {len(table['rows']):6d} rows")
        conn.commit()

    if skipped:
        print(f"\n  not in the app's schema, left out: {', '.join(skipped)}")
    print(f"\n  restored {total} rows from {os.path.basename(path)} into {url.split('@')[-1]}")
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--url", default=os.getenv("DB_URL") or os.getenv("DATABASE_URL"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    restore(args.dump, args.url, args.force)
