import os
import sys
import random
from datetime import datetime, timedelta, timezone

# Ensure project root is in sys.path so 'app' can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, project_root)

from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Unit, Symptom
from app.database import SessionLocal

def generate_random_allergen_data(
    user_email="random_user@example.com",
    days=90,
    entries_per_day=3,
    symptom_intensity_range=(0, 3)
):
    """
    Generate synthetic allergen/symptom data for a new user with no correlation
    between allergen consumption and symptom occurrence.

    Parameters
    ----------
    user_email : str, optional
        Email address of the user for whom synthetic data will be generated.
        If the user does not exist, a new user will be created.
        Default is "random_user@example.com".

    days : int, optional
        Number of past days for which data should be generated.
        Data generation starts from (current_date - days) until today.
        Default is 90 days.

    entries_per_day : int, optional
        Approximate number of allergen consumption entries per day.
        The actual number varies randomly by ±1 to simulate natural variation.
        Default is 3.

    symptom_intensity_range : tuple(int, int), optional
        Minimum and maximum range (inclusive) for randomly generated
        symptom intensity values.
        Default is (0, 3).

    Returns
    -------
    None
        This function inserts synthetic allergen and symptom logs into
        the database and prints a confirmation message. It does not
        return any value.
    """
    # Create a new database session
    db = SessionLocal()
    try:
        # Create or get user
        # Check if user already exists
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            # Create new user if not found
            user = User(email=user_email)
            db.add(user)
            db.commit()
            db.refresh(user)

        # Get allergens, units, and symptoms from database
        all_allergens = db.query(Allergen).all()
        units = db.query(Unit).all()
        symptoms = db.query(Symptom).all()

        # Filter common symptoms for more realistic logging
        common_symptoms = [s for s in symptoms if s.symptom_name.lower() in [
            "abdominal pain", "bloating", "diarrhea", "nausea", "vomiting",
            "fatigue", "headache", "brain fog"
        ]]

        # Define start date in the past
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Loop through each day
        for day_offset in range(days):
            date = start_date + timedelta(days=day_offset)

            # Randomize number of entries per day (slight variation)
            n_entries = random.randint(max(1, entries_per_day - 1), entries_per_day + 1)

            for _ in range(n_entries):
                # Randomly pick an allergen and unit
                allergen = random.choice(all_allergens)
                unit = random.choice(units)
                quantity = random.randint(1, 5)

                # Log allergen consumption at a random daytime hour
                allergen_log = AllergenLog(
                    user_id=user.user_id,
                    date_time=date + timedelta(hours=random.randint(7, 21),
                                               minutes=random.randint(0, 59)),
                    allergen_id=allergen.allergen_id,
                    quantity=quantity,
                    unit_id=unit.unit_id
                )
                db.add(allergen_log)
                db.commit()
                db.refresh(allergen_log)

                # Random symptom BEFORE exposure (control window)
                # ~10% chance, independent of allergen
                if random.random() < 0.1:
                    symptom = random.choice(common_symptoms)
                    symptom_intensity = random.randint(*symptom_intensity_range)

                    symptom_log = SymptomLog(
                        user_id=user.user_id,
                        date_time=allergen_log.date_time - timedelta(
                            minutes=random.randint(30, 180)),
                        symptom_id=symptom.symptom_id,
                        symptom_intensity=symptom_intensity
                    )
                    db.add(symptom_log)
                    db.commit()
                    db.refresh(symptom_log)

                # Random symptom AFTER exposure (causal window)
                # ~10% chance, also independent to ensure no correlation
                if random.random() < 0.1:
                    symptom = random.choice(common_symptoms)
                    symptom_intensity = random.randint(*symptom_intensity_range)

                    symptom_log = SymptomLog(
                        user_id=user.user_id,
                        date_time=allergen_log.date_time + timedelta(
                            minutes=random.randint(30, 180)),
                        symptom_id=symptom.symptom_id,
                        symptom_intensity=symptom_intensity
                    )
                    db.add(symptom_log)
                    db.commit()
                    db.refresh(symptom_log)

        # Confirmation message
        print(f"Random uncorrelated data generated for user {user_email}")

    finally:
        # Ensure DB session is always closed
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.generate_random_allergen <days> <entries_per_day>")
        sys.exit(1)

    days = int(sys.argv[1])
    entries_per_day = int(sys.argv[2])

    generate_random_allergen_data(days=days, entries_per_day=entries_per_day)

