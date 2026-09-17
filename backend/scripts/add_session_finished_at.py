"""Add workout_session.finished_at, and treat everything already there as done.

Without it there is no way to tell a session somebody is part-way through from
one they finished, so a page reload during a session stranded it — the runner
came back empty, a second session was created beside the first, and the sets
already logged were left behind. It has happened at least once here.

Backfills existing rows to their own start time rather than leaving them null,
because null now means "still open" and every one of these is long finished.

Safe to re-run.

    ./.venv/bin/python scripts/add_session_finished_at.py
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
    if "finished_at" not in cols:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE workout_session ADD COLUMN finished_at TIMESTAMPTZ"))
        print("Added workout_session.finished_at.")
    else:
        print("Column already present.")

    with engine.begin() as conn:
        n = conn.execute(text(
            "UPDATE workout_session SET finished_at = date_time "
            "WHERE finished_at IS NULL")).rowcount
    print(f"Marked {n} existing session(s) as finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
