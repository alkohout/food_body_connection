import os
import sys
import random
from datetime import datetime, timedelta, timezone
import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, project_root)

from app.models.table_class import (
    User, AllergenLog, SymptomLog, Allergen, Unit, Symptom
)
from app.database import SessionLocal

def clear_user_logs(db, user_id):
    db.query(SymptomLog).filter(
        SymptomLog.user_id == user_id
    ).delete(synchronize_session=False)

    db.query(AllergenLog).filter(
        AllergenLog.user_id == user_id
    ).delete(synchronize_session=False)

    db.commit()

def scale_quantity_to_0_3(quantity, q_min, q_max):
    if q_max == q_min:
        return 0  # or 1.5 as neutral
    return 3 * (quantity - q_min) / (q_max - q_min)

def generate_significant_allergen_data(
    user_email="significant_stat@example.com",
    days=90,
    entries_per_day=2,
    significant_allergens=("Dairy", "Peanuts", "Shellfish"),
    symptom_intensity_range=(1, 3),
    symptom_cooldown_hours=12,
):
    """
    Generate causally clean synthetic allergen → symptom data.
    Produces BOTH positive and negative labels.
    """

    rng = random.Random(42)
    np.random.seed(42)

    db = SessionLocal()
    try:
        # --------------------------------------------------
        # User
        # --------------------------------------------------
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            user = User(email=user_email)
            db.add(user)
            db.commit()
            db.refresh(user)

        # ✅ CLEAR OLD DATA
        clear_user_logs(db, user.user_id)

        units = db.query(Unit).all()
        allergens = db.query(Allergen).filter(
            Allergen.user_id == user.user_id
        ).all()

        symptoms = db.query(Symptom).filter(
            Symptom.user_id == user.user_id
        ).all()

        significant_objs = [a for a in allergens if a.allergen_name in significant_allergens]
        neutral_objs = [a for a in allergens if a.allergen_name not in significant_allergens]

        common_symptoms = [
            s for s in symptoms
            if s.symptom_name.lower() in {
                "abdominal pain", "bloating", "diarrhea",
                "nausea", "vomiting", "fatigue",
                "headache", "brain fog"
            }
        ]

        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        last_symptom_time = None

        # --------------------------------------------------
        # Generate exposures
        # --------------------------------------------------
        for day in range(days):
            day_time = start_date + timedelta(days=day)
            n_entries = rng.randint(1, entries_per_day)

            for _ in range(n_entries):
                exposure_time = day_time + timedelta(
                    hours=rng.randint(7, 20),
                    minutes=rng.randint(0, 59),
                )

                # Decide allergen type
                if rng.random() < 0.4:
                    allergen = rng.choice(significant_objs)
                    symptom_prob = 0.65
                else:
                    allergen = rng.choice(neutral_objs)
                    symptom_prob = 0.05
                
                allergen_log = AllergenLog(
                    user_id=user.user_id,
                    date_time=exposure_time,
                    allergen_id=allergen.allergen_id,
                    quantity=rng.randint(1, 4),
                    unit_id=rng.choice(units).unit_id,
                )
                db.add(allergen_log)
                db.commit()
                db.refresh(allergen_log)

                # --------------------------------------------------
                # Decide if this exposure causes a symptom
                # --------------------------------------------------
                causes_symptom = rng.random() < symptom_prob

                if not causes_symptom:
                    continue

                # Enforce symptom cooldown
                symptom_time = exposure_time + timedelta(
                    minutes=rng.randint(30, 180)
                )

                if last_symptom_time and abs(symptom_time - last_symptom_time) < timedelta(
                    hours=symptom_cooldown_hours
                ):
                    continue

                # --------------------------------------------------
                # Determine symptom intensity
                # --------------------------------------------------
                if allergen.allergen_name == "Peanuts":
                    # Base intensity 0–3
                    # Add small dose effect, but cap at 3
                    quantity = allergen_log.quantity
                    symptom_intensity = min( 3, round(scale_quantity_to_0_3(quantity, quantity.min(), quantity.max())) )
                else:
                    # Normal intensity for other allergens
                    symptom_intensity = rng.randint(0, 3)

                symptom_log = SymptomLog(
                    user_id=user.user_id,
                    date_time=symptom_time,
                    symptom_id=rng.choice(common_symptoms).symptom_id,
                    symptom_intensity=symptom_intensity,
                )

                db.add(symptom_log)
                db.commit()
                db.refresh(symptom_log)

                last_symptom_time = symptom_time

        print(
            f"Synthetic data generated for {user_email}\n"
            f"Significant allergens: {significant_allergens}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.generate_significant_allergen <days> <entries_per_day>")
        sys.exit(1)

    generate_significant_allergen_data(
        days=int(sys.argv[1]),
        entries_per_day=int(sys.argv[2]),
    )
