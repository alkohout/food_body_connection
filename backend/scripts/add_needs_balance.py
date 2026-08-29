"""Add exercise.needs_balance and set it for the standing single-leg movements.

The instability rule removed every unilateral exercise, which caught lying
work like the quad set and side-lying abduction — done one leg at a time, but
needing no balance whatsoever. Unilateral and weight-bearing-on-one-leg are
different properties and the model only had the first.

Safe to re-run: it checks for the column, and only sets rows still at the
default.

    ./venv/bin/python scripts/add_needs_balance.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from sqlalchemy import inspect, text        # noqa: E402
from app.database import engine, SessionLocal  # noqa: E402
from app.models.table_class import Exercise    # noqa: E402

# Standing on one leg is the criterion, not "done one side at a time".
BALANCE = {
    "lateral step down", "anterior step down", "split squat", "lunge",
    "single leg squat", "side kick",
}


def main() -> int:
    insp = inspect(engine)
    if "exercise" not in insp.get_table_names():
        print("exercise table does not exist yet; create_all will include the column.")
        return 0

    if "needs_balance" not in {c["name"] for c in insp.get_columns("exercise")}:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE exercise "
                "ADD COLUMN needs_balance BOOLEAN NOT NULL DEFAULT FALSE"
            ))
        print("Added exercise.needs_balance.")
    else:
        print("Column already present.")

    db = SessionLocal()
    try:
        changed = 0
        for ex in db.query(Exercise).all():
            want = (ex.exercise_name or "").strip().lower() in BALANCE
            if bool(ex.needs_balance) != want:
                ex.needs_balance = want
                changed += 1
        db.commit()
        flagged = [e.exercise_name for e in db.query(Exercise).all() if e.needs_balance]
        print(f"Updated {changed} rows. Flagged as needing balance: "
              f"{sorted(set(flagged))}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
