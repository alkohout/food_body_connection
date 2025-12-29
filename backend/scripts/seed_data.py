from datetime import datetime, timezone

# Ensure project root is in sys.path so 'app' can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Unit, Symptom
from app.core.security import hash_password
from app.database import Base, SessionLocal

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
        symptoms = [
            "Headache", 
            "Tummy Ache", 
            "Rash", 
            "Nausea", 
            "Fatigue",
            "Vomiting", 
            "Diarrhea", 
            "Consitipation",
            "Cough", 
            "Sneezing", 
            "Itching",
            "Swelling", 
            "Shortness of Breath", 
            "Dizziness", 
            "Fever"
        ]
        symptom_objects = [Symptom(symptom_name=s) for s in symptoms]
        db.add_all(symptom_objects)
        db.commit()
        for s in symptom_objects:
            db.refresh(s)

        # Create allergens
                # Create allergens (standard list)
        allergens = [
            "Peanuts",
            "Tree Nuts",
            "Dairy",
            "Eggs",
            "Fish",
            "Shellfish",
            "Gluten",
            "Soy",
            "Sesame",
            "Mustard"
        ]
        allergen_objects = [Allergen(allergen_name=a) for a in allergens]
        db.add_all(allergen_objects)
        db.commit()
        for a in allergen_objects:
            db.refresh(a)


        # Create base units
        units = ["grams", 
                 "ml", 
                 "pieces", 
                 "tablespoons", 
                 "teaspoons", 
                 "cups"
        ]
        unit_objects = [Unit(unit_name=u) for u in units]
        db.add_all(unit_objects)
        db.commit()
        for u in unit_objects:
            db.refresh(u)

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

