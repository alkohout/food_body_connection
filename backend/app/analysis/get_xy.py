from app.schemas.analyse import X, y
import pandas as pd

def get_xy(
    allergen_df: pd.DataFrame,
    symptom_df: pd.DataFrame,
): 
    """
    Constructs the feature matrix X for prediction based on allergen and symptom dataframes.
    """
    # Example implementation - actual feature engineering will depend on the model requirements
    rows = []
    targets = []
    for _, allergen_event in allergen_df.iterrows():

        exposure_time = allergen_event["date_time"]
        allergen_id = allergen_event["allergen_id"]
        volume = allergen_event.get("volume", 0.0) # return 0.0 if volume not present

        # Find symptoms that occurred after this allergen exposure
        window_end = exposure_time + pd.Timedelta(hours=24)
        relevant_symptoms = symptom_df[
            (symptom_df["date_time"] > exposure_time) &
            (symptom_df["date_time"] <= window_end)
        ]

        row = X(
            allergen_id=allergen_id,
            exposure_volume=volume,
            hours_since_exposure=24,
        )
        rows.append(row)

        targets = y(
            symptom_occurred=int(len(relevant_symptoms) > 0),
            symptom_max_intensity=(
                relevant_symptoms["symptom_intensity"].max()
                if not relevant_symptoms.empty
                else None
            ),
        )

    return pd.DataFrame(rows), pd.DataFrame(targets) 