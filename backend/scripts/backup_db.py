"""Take a copy of the database that does not live in anybody's cloud account.

There were three layers of protection here and a gap between them. Neon's
point-in-time restore covers a mistake noticed quickly, inside the same
account. An Oracle volume backup covers the machine, which does not hold the
data. And the one artifact under the owner's control was seven months stale,
missing eleven of seventeen tables, and pointed at a database host that had
been decommissioned — a script that fails every time it runs is worse than no
script, because it is why you believe you are covered.

Read through raw SQL rather than the ORM on purpose. Several columns are
Fernet-encrypted at the application layer, and the ORM would decrypt them on
the way out — writing plaintext health data to a file that then gets copied
around. Raw reads keep the ciphertext, so the dump is worthless without
FERNET_KEY, which is the property you want.

Which also means: back up FERNET_KEY, and do not keep it beside the dumps. A
backup you cannot read is not a backup.

    ./.venv/bin/python scripts/backup_db.py [--out DIR] [--keep N]
"""
import argparse
import datetime as dt
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from sqlalchemy import inspect, text        # noqa: E402

from app.database import engine             # noqa: E402

FORMAT = 1


def _plain(value):
    """A JSON-safe form that Postgres will accept back unchanged."""
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        import base64
        return {"__b64__": base64.b64encode(bytes(value)).decode()}
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def take(out_dir, keep):
    os.makedirs(out_dir, exist_ok=True)
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    dump = {"format": FORMAT,
            "taken_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "tables": {}}
    total = 0
    with engine.connect() as conn:
        for name in tables:
            result = conn.execute(text(f'SELECT * FROM "{name}"'))
            cols = list(result.keys())
            rows = [[_plain(v) for v in row] for row in result]
            dump["tables"][name] = {"columns": cols, "rows": rows}
            total += len(rows)
            print(f"  {name:22s} {len(rows):6d} rows")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(out_dir, f"fbc-{stamp}.json.gz")
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(dump, fh)
    size = os.path.getsize(path)
    print(f"\n  wrote {path}  ({size/1024:.0f} kB, {total} rows, {len(tables)} tables)")

    # Rotate. Oldest first, so a run that fails part-way never deletes the
    # last good copy before it has written a new one.
    existing = sorted(f for f in os.listdir(out_dir)
                      if f.startswith("fbc-") and f.endswith(".json.gz"))
    for stale in existing[:-keep] if keep else []:
        os.remove(os.path.join(out_dir, stale))
        print(f"  removed {stale}")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.expanduser("~/fbc-backups"))
    ap.add_argument("--keep", type=int, default=30)
    args = ap.parse_args()
    take(args.out, args.keep)
