"""Add exercise.exertion and exercise.floor_based, and set them.

A symptom can limit what a session may contain rather than how much load it
carries: with a migraine the problem is bending down and exerting at all, not
the weight on the bar. Neither property could be derived from what the model
already had — category and equipment say nothing about whether you have to get
on the floor.

1 gentle, 2 moderate, 3 demanding. Anything unlisted stays at the 2 default.

    ./venv/bin/python scripts/add_exercise_effort.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from sqlalchemy import inspect, text          # noqa: E402
from app.database import engine, SessionLocal # noqa: E402
from app.models.table_class import Exercise   # noqa: E402

# The table itself lives in the catalogue now. It was duplicated here, which
# meant it only ever reached accounts this script was run against — everything
# seeded afterwards silently used the column defaults.
from app.data.exercise_library import EFFORT   # noqa: E402



def main() -> int:
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("exercise")}
    with engine.begin() as conn:
        if "exertion" not in cols:
            conn.execute(text("ALTER TABLE exercise ADD COLUMN exertion INTEGER NOT NULL DEFAULT 2"))
            print("Added exercise.exertion.")
        if "floor_based" not in cols:
            conn.execute(text("ALTER TABLE exercise ADD COLUMN floor_based BOOLEAN NOT NULL DEFAULT FALSE"))
            print("Added exercise.floor_based.")

    db = SessionLocal()
    try:
        changed, unlisted = 0, set()
        for ex in db.query(Exercise).all():
            key = (ex.exercise_name or "").strip().lower()
            if key not in EFFORT:
                unlisted.add(ex.exercise_name)
                continue
            exertion, floor = EFFORT[key]
            if ex.exertion != exertion or bool(ex.floor_based) != floor:
                ex.exertion, ex.floor_based = exertion, floor
                changed += 1
        db.commit()
        print(f"Set effort on {changed} rows.")
        if unlisted:
            print(f"Left at the default (2, not floor-based): {sorted(unlisted)}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
