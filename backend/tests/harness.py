"""A throwaway database with one trained-up user in it.

Every check in this suite used to be a one-off script pasted into a shell,
which meant each one was written, run once and lost — so the same regressions
had to be rediscovered rather than caught. They run against in-memory SQLite
rather than the real database: no network, no rollback to get wrong, and a
whole matrix in the time one build used to take against Neon.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from sqlalchemy import create_engine                      # noqa: E402
from sqlalchemy.orm import sessionmaker                   # noqa: E402

from app.data.exercise_library import EFFORT, LIBRARY     # noqa: E402
from app.models.table_class import (                      # noqa: E402
    Base, Exercise, SetLog, Symptom, SymptomLog, TrainingProfile, User,
    WorkoutSession)

START = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)   # a Monday

KNEE_SYMPTOMS = [
    "Knee pain - left lateral", "Knee pain - left medial",
    "Knee pain - left posterior", "Knee swelling - left",
    "Knee giving way - left", "Headache", "Fatigue",
]


class Clock(datetime):
    """Stands in for datetime so the weekday and the deload week are testable."""
    _now = START.replace(tzinfo=None)

    @classmethod
    def utcnow(cls):
        return cls._now


def fresh(focus="knee", kit=("band", "dumbbell", "tube"), spacing="daily",
          history_days=30, broad_history=True, score=1):
    """A session bound to a new in-memory database, plus the ids you need."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    user = User(email="t@example.invalid", password_hash="x")
    db.add(user)
    db.flush()
    for name, cat, target, equip, uni, iso, cues, url in LIBRARY:
        exertion, floor = EFFORT.get(name, (2, False))
        db.add(Exercise(user_id=user.user_id, exercise_name=name, category=cat,
                        target=target, equipment=equip, is_unilateral=uni,
                        is_isometric=iso, form_cues=cues, video_url=url,
                        exertion=exertion, floor_based=floor))
    db.add(TrainingProfile(
        user_id=user.user_id, focus=focus, dumbbell_bar_kg=0.0,
        equipment_json=json.dumps({
            "available": list(kit), "bands": [7.5, 15.0, 30.0, 50.0],
            "strength_spacing": spacing,
            "plates": {"3.0": 8, "2.5": 4, "1.25": 4}})))
    for name in KNEE_SYMPTOMS:
        db.add(Symptom(user_id=user.user_id, symptom_name=name))
    db.flush()

    by_name = {e.exercise_name: e for e in
               db.query(Exercise).filter(Exercise.user_id == user.user_id).all()}
    logged = [r[0] for r in LIBRARY if r[1] in ("strength", "martial", "mobility")] \
        if broad_history else ["Spanish Squat", "Push Up", "Plank"]
    for i in range(history_days):
        s = WorkoutSession(user_id=user.user_id, date_time=START + timedelta(days=i),
                           session_type="strength", next_day_knee=score)
        db.add(s)
        db.flush()
        for name in logged:
            db.add(SetLog(user_id=user.user_id, session_id=s.session_id,
                          exercise_id=by_name[name].exercise_id, set_number=1,
                          reps=10, hold_seconds=30, pain=1))
    db.flush()
    return db, user.user_id, by_name, {
        s.symptom_name: s.symptom_id for s in
        db.query(Symptom).filter(Symptom.user_id == user.user_id).all()}


def log_symptom(db, user_id, symptom_id, level, hours_ago=3):
    db.query(SymptomLog).filter(SymptomLog.user_id == user_id).delete()
    if symptom_id is not None:
        db.add(SymptomLog(user_id=user_id, symptom_id=symptom_id,
                          date_time=Clock._now - timedelta(hours=hours_ago),
                          symptom_intensity=level))
    db.flush()


def at(day_offset, hour=3):
    """Move the clock, and hand back the moment for readability."""
    Clock._now = (START + timedelta(days=day_offset)).replace(tzinfo=None, hour=hour)
    return Clock._now
