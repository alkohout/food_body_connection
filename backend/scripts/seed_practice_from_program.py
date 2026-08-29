"""Turn a hard-coded programme practice into editable practice_item rows.

The tai chi and kung fu routine used to live inside the knee programme. It is
personal, so it now lives in practice_item where its owner can change it. This
moves it across once, for accounts that were relying on the old default.

Safe to re-run: it does nothing for a user who already has practice rows.

    ./venv/bin/python scripts/seed_practice_from_program.py <user_id>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.database import SessionLocal                      # noqa: E402
from app.models.table_class import Exercise, PracticeItem  # noqa: E402

# name, slot, scheme, sets, low, high, alternates_with
ROUTINE = [
    ("Tai Chi Exercises", "before", "check", 1, 0, 0, None),
    ("Tai Chi Form 42", "before", "check", 1, 0, 0, "Tai Chi Form 37"),
    ("Tai Chi Sword", "before", "check", 1, 0, 0, None),
    ("Stretches", "after", "check", 1, 0, 0, None),
    ("Kung Fu Pattern", "after", "check", 1, 0, 0, None),
    ("Side Kick", "after", "reps", 2, 10, 20, None),
]


def main(user_id: int) -> int:
    db = SessionLocal()
    try:
        if db.query(PracticeItem).filter(PracticeItem.user_id == user_id).count():
            print(f"User {user_id} already has a practice routine. Nothing to do.")
            return 0

        by_name = {
            e.exercise_name.strip().lower(): e
            for e in db.query(Exercise).filter(Exercise.user_id == user_id).all()
        }
        counters = {"before": 0, "after": 0}
        added, missing = 0, []
        for name, slot, scheme, sets, low, high, alt in ROUTINE:
            ex = by_name.get(name.strip().lower())
            if ex is None:
                missing.append(name)
                continue
            alt_ex = by_name.get(alt.strip().lower()) if alt else None
            db.add(PracticeItem(
                user_id=user_id, exercise_id=ex.exercise_id, slot=slot,
                position=counters[slot], scheme=scheme, sets=sets, low=low,
                high=high,
                alternates_with_id=alt_ex.exercise_id if alt_ex else None,
            ))
            counters[slot] += 1
            added += 1
        db.commit()
        print(f"Added {added} practice items for user {user_id}.")
        if missing:
            print(f"Not in their library, skipped: {', '.join(missing)}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: seed_practice_from_program.py <user_id>")
    raise SystemExit(main(int(sys.argv[1])))
