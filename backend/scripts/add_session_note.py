"""Add workout_session.session_note, for a note the person writes themselves.

The existing `notes` column is not free for this. The session runner already
writes into it — "Skipped: Ankle Rock-Overs, Side Kick" — so it is a generated
record of what came out of the plan, present on 40 of the 71 sessions logged
here. Sharing one column would mean a sentence typed by hand and the skipped
list overwriting each other, and neither is recoverable afterwards.

Encrypted at the application layer like every other free-text column, so the
type is TEXT here and the ciphertext is what lands in it.

Additive and safe to run before the matching code is deployed: older code does
not know the column exists and ignores it.

Safe to re-run.

    ./.venv/bin/python scripts/add_session_note.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from sqlalchemy import inspect, text        # noqa: E402

from app.database import engine             # noqa: E402


def main() -> int:
    insp = inspect(engine)
    if "workout_session" not in insp.get_table_names():
        print("workout_session does not exist yet; create_all will include the column.")
        return 0

    cols = {c["name"] for c in insp.get_columns("workout_session")}
    if "session_note" in cols:
        print("Column already present. Nothing to do.")
        return 0

    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE workout_session ADD COLUMN session_note TEXT"))
    print("Added workout_session.session_note.")

    # Nothing to backfill. Null means "nothing written", which is the truth for
    # every session so far, and the generated `notes` column is left exactly as
    # it is rather than being split on a guess about which half is which.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
