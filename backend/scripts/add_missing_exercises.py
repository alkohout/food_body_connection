"""Add any catalogue exercise missing from the libraries of existing users.

The programme points at exercise rows by name, so an exercise added to the
catalogue after someone was seeded does not reach them: their session either
substitutes around it or leaves a gap. This closes that, and is the same thing
the seed endpoint does for a new account.

Only touches accounts that already have exercises. An account with an empty
library has not started, and will get the whole catalogue from the normal
seed when it does.

Safe to re-run: matches on name, and never edits an exercise already there.

    ./.venv/bin/python scripts/add_missing_exercises.py [user_id]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.database import SessionLocal                # noqa: E402
from app.models.table_class import Exercise          # noqa: E402
from app.data.exercise_library import EFFORT, LIBRARY    # noqa: E402


def main():
    only = int(sys.argv[1]) if len(sys.argv) > 1 else None
    db = SessionLocal()
    rows, effort = LIBRARY, EFFORT
    try:
        users = {e.user_id for e in db.query(Exercise).all()}
        if only is not None:
            users &= {only}
        for user_id in sorted(users):
            have = {
                e.exercise_name.strip().lower()
                for e in db.query(Exercise).filter(Exercise.user_id == user_id).all()
            }
            added = 0
            for name, category, target, equip, uni, iso, cues, url in rows:
                if name.strip().lower() in have:
                    continue
                exertion, floor = effort.get(name, (2, False))
                db.add(Exercise(
                    user_id=user_id, exercise_name=name, category=category,
                    target=target, equipment=equip, is_unilateral=uni,
                    is_isometric=iso, form_cues=cues, video_url=url,
                    exertion=exertion, floor_based=floor,
                ))
                added += 1
            db.commit()
            print(f"user {user_id}: added {added} of {len(rows)}")
        if not users:
            print("no matching user with an existing library")
    finally:
        db.close()


if __name__ == "__main__":
    main()
