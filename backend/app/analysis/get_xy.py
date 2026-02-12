from app.schemas.analyse import X as XModel, y as YModel
from app.data.analysis_data import get_allergen_name_str
from sqlalchemy.orm import Session

import pandas as pd

def get_xy(db: Session, current_user: int, allergen_df: pd.DataFrame, symptom_df: pd.DataFrame, lag_window: tuple[int, int] = (0, 6)):
    """
    Constructs the feature matrix X and target matrix y 
    based on allergen exposure and symptom dataframes.

    Parameters:
    - db: Active database session
    - current_user: ID of the current user
    - allergen_df: DataFrame containing allergen exposure events
    - symptom_df: DataFrame containing symptom records
    - lag_window: Time window (in hours) after exposure to check for symptoms
                  Default = (0, 6) meaning between 0 and 6 hours after exposure

    Returns:
    - X_df: Feature DataFrame
    - y_df: Target DataFrame
    """

    # Lists to collect feature (X) and target (y) rows
    rows = []
    targets = []

    # Iterate over each allergen exposure event
    for _, allergen_event in allergen_df.iterrows():

        # Timestamp of allergen exposure
        exposure_time = allergen_event["date_time"]

        # Allergen ID for lookup
        allergen_id = allergen_event["allergen_id"]

        # Convert allergen ID to human-readable allergen name
        allergen_name = get_allergen_name_str(db, current_user, allergen_id) 

        # Exposure volume (default to 0.0 if missing)
        volume = allergen_event.get("volume", 0.0)

        # Define lag window (hours after exposure)
        lag_start, lag_end = lag_window

        # Calculate start and end timestamps of the symptom window
        window_start = exposure_time + pd.Timedelta(hours=lag_start)
        window_end   = exposure_time + pd.Timedelta(hours=lag_end)

        # Filter symptom records that occurred within the lag window
        relevant_symptoms = symptom_df[
            (symptom_df["date_time"] > window_start) &
            (symptom_df["date_time"] <= window_end)
        ]

        # -------------------------
        # Construct Feature Row (X)
        # -------------------------
        rows.append(
            XModel(
                allergen_name=allergen_name,              # Categorical allergen name
                exposure_volume=volume,                   # Numeric exposure amount
                hours_since_exposure=(lag_start + lag_end) / 2  # Midpoint of lag window
            )
        )

        # -------------------------
        # Construct Target Row (y)
        # -------------------------
        targets.append(
            YModel(
                # 1 if at least one symptom occurred in the window, else 0
                symptom_occurred=int(len(relevant_symptoms) > 0),

                # Maximum symptom intensity within window (None if no symptoms)
                symptom_max_intensity=(
                    relevant_symptoms["symptom_intensity"].max()
                    if not relevant_symptoms.empty
                    else None
                ),
            )
        )

    # Convert lists of Pydantic objects into pandas DataFrames
    # This is done AFTER the loop for efficiency
    X_df = pd.DataFrame([r.model_dump() for r in rows])
    y_df = pd.DataFrame([t.model_dump() for t in targets])

    # Return feature and target DataFrames
    return X_df, y_df