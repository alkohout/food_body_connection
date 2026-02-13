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
    """
    Delete all allergen and symptom logs for a specific user.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy database session.

    user_id : int
        ID of the user whose logs should be deleted.

    Returns
    -------
    None
        Deletes records from the database and commits the transaction.
    """

    # Delete all symptom logs for the given user
    db.query(SymptomLog).filter(
        SymptomLog.user_id == user_id
    ).delete(synchronize_session=False)

    # Delete all allergen logs for the given user
    db.query(AllergenLog).filter(
        AllergenLog.user_id == user_id
    ).delete(synchronize_session=False)

    # Commit changes to persist deletions
    db.commit()

def clear_user_tables(db, user_id):
    """
    Delete all allergen and symptom logs for a specific user.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy database session.

    user_id : int
        ID of the user whose logs should be deleted.

    Returns
    -------
    None
        Deletes records from the database and commits the transaction.
    """

    db.query(Symptom).filter(
        Symptom.user_id == user_id
    ).delete(synchronize_session=False) 

    db.query(Allergen).filter(
        Allergen.user_id == user_id
    ).delete(synchronize_session=False)

    # Commit changes to persist deletions
    db.commit()


def scale_quantity_to_0_3(quantity, q_min, q_max):
    """
    Linearly scale a quantity value to a 0–3 range.

    Parameters
    ----------
    quantity : float or int
        The original quantity value to be scaled.

    q_min : float or int
        The minimum quantity value in the dataset.

    q_max : float or int
        The maximum quantity value in the dataset.

    Returns
    -------
    float
        Scaled value between 0 and 3. If q_max equals q_min,
        returns 0 to avoid division by zero.
    """

    # Avoid division by zero if all quantities are equal
    if q_max == q_min:
        return 0  # or 1.5 as neutral midpoint

    # Perform min-max scaling to 0–3 range
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

    Parameters
    ----------
    user_email : str, optional
        Email of the user for whom synthetic data will be generated.
        If the user does not exist, a new one will be created.

    days : int, optional
        Number of past days for which exposure data will be generated.

    entries_per_day : int, optional
        Maximum number of allergen exposures per day.

    significant_allergens : tuple[str], optional
        Allergen names that should have a strong causal relationship
        with symptom generation.

    symptom_intensity_range : tuple[int, int], optional
        Range for symptom intensity (currently partially used; some
        allergens use dose-based scaling instead).

    symptom_cooldown_hours : int, optional
        Minimum number of hours required between two symptoms
        to prevent overlapping or clustered symptom events.

    Returns
    -------
    None
        Inserts synthetic allergen and symptom logs into the database
        and prints a summary message.
    """

    # Seed randomness for reproducibility
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

        # Fetch related objects
        units = db.query(Unit).all()
        allergens = db.query(Allergen).filter(
            Allergen.user_id == user.user_id
        ).all()

        symptoms = db.query(Symptom).filter(
            Symptom.user_id == user.user_id
        ).all()

        # Separate significant vs neutral allergens
        significant_objs = [a for a in allergens if a.allergen_name in significant_allergens]
        neutral_objs = [a for a in allergens if a.allergen_name not in significant_allergens]

        # Filter realistic symptom types
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
        conversions = [1, 1, 1000, 15, 5, 240]

        for day in range(days):
            day_time = start_date + timedelta(days=day)
            n_entries = rng.randint(1, entries_per_day)

            for _ in range(n_entries):
                # Random exposure time during day
                exposure_time = day_time + timedelta(
                    hours=rng.randint(7, 20),
                    minutes=rng.randint(0, 59),
                )

                # Decide allergen type (significant vs neutral)
                if rng.random() < 0.4:
                    allergen = rng.choice(significant_objs)
                    symptom_prob = 0.6  # Strong causal probability
                else:
                    allergen = rng.choice(neutral_objs)
                    symptom_prob = 0.05  # Weak/no causal probability

                # Generate dose volume
                target_volume = rng.uniform(0, 1000)
                unit_idx = rng.randrange(len(units))
                conversion = conversions[unit_idx]
                quantity = target_volume / conversion

                # Log allergen exposure
                allergen_log = AllergenLog(
                    user_id=user.user_id,
                    date_time=exposure_time,
                    allergen_id=allergen.allergen_id,
                    quantity=quantity,
                    unit_id=units[unit_idx].unit_id,
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
                    # Dose-dependent intensity (scaled 0–3)
                    symptom_intensity = min(
                        3,
                        round(scale_quantity_to_0_3(target_volume, 0, 1000))
                    )
                else:
                    # Random intensity for other allergens
                    symptom_intensity = rng.randint(0, 3)

                # Log symptom
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
