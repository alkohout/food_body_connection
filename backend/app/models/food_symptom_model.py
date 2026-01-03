# backend/app/models/food_symptom_model.py

from app.database import SessionLocal
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

from sqlalchemy.orm import Session
from app.models.table_class import AllergenLog, Allergen, Unit
from app.models.table_class import SymptomLog, Symptom
import pandas as pd

db = SessionLocal()

# Query allergen log with related allergen name and unit conversion
query = (
    db.query(
        AllergenLog.date_time.label("allergen_date_time"),
        Allergen.allergen_name.label("allergen_name"),
        AllergenLog.quantity.label("quantity"),
        Unit.unit_conversion.label("unit_conversion")
    )
    .join(Allergen, AllergenLog.allergen_id == Allergen.allergen_id)
    .outerjoin(Unit, AllergenLog.unit_id == Unit.unit_id)
)

allergen_df = pd.read_sql(query.statement, db.bind)

# Query symptom log with symptom name and intensity
query = (
    db.query(
        SymptomLog.date_time.label("symptom_date_time"),
        Symptom.symptom_name.label("symptom_name"),
        Symptom.symptom_group.label("symptom_group"),
        SymptomLog.symptom_intensity.label("intensity")
    )
    .join(Symptom, SymptomLog.symptom_id == Symptom.symptom_id)
)

symptom_df = pd.read_sql(query.statement, db.bind)
db.close()

allergen_df["allergen_date_time"] = pd.to_datetime(allergen_df["allergen_date_time"], utc=True)
symptom_df["symptom_date_time"] = pd.to_datetime(symptom_df["symptom_date_time"], utc=True)

df = pd.concat([allergen_df, symptom_df], axis=1)
df['volume'] = df['quantity'] * df['unit_conversion']

df = (
    df
    .groupby(
        [
            "allergen_date_time",
            "allergen_name",
            "quantity",
            "unit_conversion",
            "volume",
        ],
        as_index=False
    )
    .agg(
        symptom_occurred=("intensity", lambda x: (x > 0).any()),
        max_intensity=("intensity", "max"),
        n_symptoms=("intensity", lambda x: (x > 0).sum()),
    )
)

X = df.drop(columns=["symptom_occurred", "allergen_date_time", "quantity", "unit_conversion"])
X = pd.get_dummies(df[["allergen_name"]], drop_first=True)
y = df["symptom_occurred"]

print(f"Features shape: {X.shape}, Target shape: {y.shape}")

# ------------------------
# 4. Train model
# ------------------------
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X, y)

print("Model training complete!")

# ------------------------
# 5. Save trained model
# ------------------------
MODEL_PATH = "food_symptom_model.pkl"
joblib.dump(model, MODEL_PATH)
print(f"Model saved to {MODEL_PATH}")

