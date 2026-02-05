import os
import sys
from datetime import datetime, timezone

# Ensure project root is in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, project_root)

from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Unit, Symptom
from app.core.security import hash_password
from app.database import SessionLocal


def create_user(db, email):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def main():

    db = SessionLocal()

    # ---------------------------------------------------
    # 1. Create Users
    # ---------------------------------------------------
    random_user = create_user(db, "random_user@example.com")
    significant_user = create_user(db, "significant_stat@example.com")
    test_user = create_user(db, "test@example.com")

    users = db.query(User).all()

    # ---------------------------------------------------
    # 2. Symptom Definitions (Global List)
    # ---------------------------------------------------
    SYMPTOM_GROUPS = {
        "Gastrointestinal": [
            "Abdominal Pain","Bloating","Constipation","Diarrhea","Gas","Heartburn",
            "Indigestion","Nausea","Vomiting","Loss of Appetite","Increased Appetite"
        ],
        "Neurological": [
            "Headache","Migraine","Dizziness","Vertigo","Brain Fog","Light Sensitivity",
            "Sound Sensitivity","Visual Disturbances","Tingling","Numbness"
        ],
        "Skin": ["Rash","Hives","Itching","Eczema","Acne","Flushing","Swelling","Dry Skin"],
        "Respiratory": ["Cough","Sneezing","Runny Nose","Nasal Congestion","Shortness of Breath","Chest Tightness","Wheezing"],
        "Cardiovascular": ["Palpitations","Rapid Heart Rate","Low Blood Pressure","High Blood Pressure","Cold Hands or Feet"],
        "Systemic": ["Fatigue","Fever","Chills","Body Aches","Joint Pain","Muscle Pain","Weakness"],
        "Sleep": ["Difficulty Falling Asleep","Difficulty Staying Asleep","Unrefreshing Sleep","Night Sweats"],
        "Mood/Cognitive": ["Anxiety","Depression","Irritability","Low Mood","Poor Concentration"],
        "Menstrual": ["Cramps","Cycle"]
    }

    # ---------------------------------------------------
    # 3. Allergen Definitions (Global List)
    # ---------------------------------------------------
    ALLERGENS = [
        "Dairy","Eggs","Peanuts","Tree Nuts","Soy","Gluten","Fish","Shellfish",
        "Sesame","Mustard","Celery","Lupin","Sulphites",
        "Tomatoes","Potatoes","Nightshades","Legumes","Chickpeas","Lentils",
        "MSG","Artificial Sweeteners","Aspartame","Food Colorings","Preservatives",
        "Caffeine","Alcohol","Red Wine","Beer",
        "Pollen","Dust Mites","Mold","Pet Dander","Fragrances",
        "Cleaning Products","Smoke","Perfume"
    ]

    # ---------------------------------------------------
    # 4. Seed Allergens & Symptoms For Each User
    # ---------------------------------------------------
    for user in users:

        # Seed Symptoms
        for group_name, symptoms in SYMPTOM_GROUPS.items():
            for s in symptoms:
                db.add(Symptom(
                    symptom_name=s,
                    symptom_group=group_name,
                    user_id=user.user_id
                ))

        # Seed Allergens
        for a in ALLERGENS:
            db.add(Allergen(
                allergen_name=a,
                user_id=user.user_id
            ))

    db.commit()

    # ---------------------------------------------------
    # 5. Seed Units (Once)
    # ---------------------------------------------------
    units = ["grams", "ml", "liters", "tablespoons", "teaspoons", "cups"]
    conversions = [1, 1, 1000, 15, 5, 240]

    for name, conv in zip(units, conversions):
        db.add(Unit(unit_name=name, unit_conversion=conv))

    db.commit()

    # ---------------------------------------------------
    # 6. Add demo logs for test@example.com
    # ---------------------------------------------------
    db.add(AllergenLog(
        user_id=test_user.user_id,
        date_time=datetime.now(timezone.utc),
        allergen_id=1,
        quantity=2,
        unit_id=1
    ))

    db.add(SymptomLog(
        user_id=test_user.user_id,
        date_time=datetime.now(timezone.utc),
        symptom_id=1,
        symptom_intensity=3
    ))

    db.commit()

    print("Seed data created successfully!")


if __name__ == "__main__":
    main()