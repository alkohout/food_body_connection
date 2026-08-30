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

# name -> (exertion, floor_based)
EFFORT = {
    # Gentle and upright: what is left on a bad day.
    "tai chi exercises": (1, False),
    "tai chi form 42": (1, False),
    "tai chi form 37": (1, False),
    "stretches": (1, False),
    "single leg balance": (1, False),
    "quad set": (1, True),
    "terminal knee extension": (1, False),
    "tibialis raise": (1, False),
    "standing calf raise": (1, False),
    "band pull apart": (1, False),
    "prone y raise": (1, True),
    "clamshell": (1, True),
    "side lying hip abduction": (1, True),
    "standing hip abduction": (1, False),
    "lateral band walk": (2, False),

    # Moderate.
    "tai chi sword": (2, False),
    "wall sit": (2, False),
    "spanish squat": (2, False),
    "supported single leg squat": (2, False),
    "wide leg squat": (2, False),
    "glute bridge": (2, True),
    "single leg glute bridge": (2, True),
    "bird dog": (2, True),
    "dead bug": (2, True),
    "sit up": (2, True),
    "plank": (2, True),
    "side plank": (2, True),
    "incline push up": (2, False),
    "push up": (2, True),
    "tricep dip": (2, False),
    "bicep curl": (2, False),
    "dumbbell row": (2, True),
    "dumbbell shoulder press": (2, False),
    "dumbbell floor press": (2, True),

    # Demanding.
    "kung fu pattern": (3, False),
    "side kick": (3, False),
    "goblet squat": (3, False),
    "box squat": (3, False),
    "split squat": (3, False),
    "lunge": (3, False),
    "single leg squat": (3, False),
    "lateral step down": (3, False),
    "anterior step down": (3, False),
    "romanian deadlift": (3, False),
    "pike push up": (3, True),
}


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
