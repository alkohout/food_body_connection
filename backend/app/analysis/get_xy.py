from app.schemas.analyse import X as XModel, y as YModel
from app.data.analysis_data import get_allergen
from sqlalchemy.orm import Session

import pandas as pd

def get_xy(db: Session, allergen_df: pd.DataFrame, symptom_df: pd.DataFrame):
    """
    Constructs the feature matrix X for prediction based on allergen and symptom dataframes.
    """
    rows = []
    targets = []

    for _, allergen_event in allergen_df.iterrows():
        exposure_time = allergen_event["date_time"]
        allergen_id = allergen_event["allergen_id"]
        allergen_name = get_allergen(db, allergen_id) 
        volume = allergen_event.get("volume", 0.0)  # return 0.0 if volume not present

        # Find symptoms that occurred within 24 hours
        window_end = exposure_time + pd.Timedelta(hours=24)
        relevant_symptoms = symptom_df[
            (symptom_df["date_time"] > exposure_time) &
            (symptom_df["date_time"] <= window_end)
        ]

        # Append X row
        rows.append(
            XModel(
                allergen_name=allergen_name,
                exposure_volume=volume,
                hours_since_exposure=24,
            )
        )

        # Append y row
        targets.append(
            YModel(
                symptom_occurred=int(len(relevant_symptoms) > 0),
                symptom_max_intensity=(
                    relevant_symptoms["symptom_intensity"].max()
                    if not relevant_symptoms.empty
                    else None
                ),
            )
        )

    # Convert lists of Pydantic objects to DataFrames **after the loop**
    X_df = pd.DataFrame([r.model_dump() for r in rows])
    y_df = pd.DataFrame([t.model_dump() for t in targets])

    return X_df, y_df
