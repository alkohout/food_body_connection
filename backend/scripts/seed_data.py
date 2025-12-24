from click import DateTime
from traitlets import Integer
from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Unit, Symptom
from app.core.security import hash_password
from app.database import Base, SessionLocal
from datetime import datetime, timezone

def main():

    # Create a session
    db = SessionLocal()

    try:
        # Create a test user
        test_user = User(
            email="test@example.com",
            password_hash=hash_password("password123")
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)  # so test_user.user_id is populated

        # Create symptoms
        headache = Symptom(symptom_name="Headache")
        tummy_ache = Symptom(symptom_name="Tummy Ache")
        db.add_all([headache,tummy_ache])
        db.commit()
        db.refresh(tummy_ache)
        db.refresh(headache)

        # Create allergens
        peanut = Allergen(allergen_name="Peanuts")
        dairy = Allergen(allergen_name="Dairy")
        db.add_all([peanut, dairy])
        db.commit()
        db.refresh(peanut)
        db.refresh(dairy)

        # Create base units
        grams = Unit(unit_name="grams")
        ml = Unit(unit_name="ml")
        db.add_all([grams, ml])
        db.commit()
        db.refresh(grams)
        db.refresh(ml)

        # Create some allergen diary entries
        entry = AllergenLog(
            user_id = test_user.user_id,
            date_time = datetime.now(timezone.utc),
            allergen_id = 1,
            quantity = 2,
            unit_id = 1
        )
        db.add(entry)

        # Create some symptom diary entries
        entry = SymptomLog(
            user_id = test_user.user_id,
            date_time = datetime.now(timezone.utc),
            symptom_id = 1, 
            symptom_intensity = 3
        )
        db.add(entry)

        # Commit all diary entries
        db.commit()

        print("ed data created successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    main()

