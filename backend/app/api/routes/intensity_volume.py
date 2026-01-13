# app/api/routes/intensity_volume.py
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.database import get_db
from app.models.table_class import User
from app.data.analysis_data import get_all_symptom_events_df, get_all_allergen_events_df, get_unit
from datetime import datetime, timedelta
import pandas as pd
import seaborn as sns
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from starlette.responses import StreamingResponse
import logging
import traceback
from fastapi import HTTPException
from io import BytesIO
import pandas as pd

logger = logging.getLogger("backend/app/api/routes/intensity_volume.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get('/intensity_volume')
def intensity_volume(
    allergen_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try: 
        
        # --- Fetch allergen and symptom events (already DataFrames) ---
        allergen_df = get_all_allergen_events_df(
            db,
            current_user.user_id,
            allergen_name=allergen_name
        )

        symptom_df = get_all_symptom_events_df(
            db,
            current_user.user_id
        )

        # --- Guard against empty data ---
        if allergen_df.empty:
            logger.warning("No allergen events found")
            return None  # or empty plot

        # Ensure datetime dtype
        allergen_df["date_time"] = pd.to_datetime(allergen_df["date_time"], utc=True)
        symptom_df["date_time"] = pd.to_datetime(symptom_df["date_time"], utc=True)

        # --- Determine overall min/max dates ---
        start_dt = allergen_df["date_time"].min()
        end_dt = allergen_df["date_time"].max()

        logger.info("Generating EDA plot for user_id=%d", current_user.user_id)
        logger.info("Start date: %s, End date: %s", start_dt, end_dt)
        logger.info(
            "Allergen events: %d, Symptom events: %d",
            len(allergen_df),
            len(symptom_df),
        )

        # --- Pre-sort for faster window filtering ---
        symptom_df = symptom_df.sort_values("date_time")

        rows = []

        for _, allergen in allergen_df.iterrows():
            start = allergen["date_time"]
            end = start + timedelta(hours=24)

            # Filter symptoms in window
            window_symptoms = symptom_df[
                (symptom_df["date_time"] >= start) &
                (symptom_df["date_time"] <= end)
            ]

            # Sum intensity
            total_intensity = window_symptoms["symptom_intensity"].fillna(0).sum()

            # Emphasize clusters
            burden_score = total_intensity

            rows.append({
                "volume": allergen["volume"],
                "burden_score": burden_score,
            })

        df = pd.DataFrame(rows)
        logger.info("Valid rows for plot: %d", len(df))
        logger.info(df.head(74))

        # --- Plotting ---
        sns.set(style="whitegrid")
        fig, axes = plt.subplots(1, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3]})

        # Sort by count descending and take top 10
        sns.scatterplot(data=df, x="volume", y="burden_score", ax=axes)
        axes.set_title(f"Total symptom Burden Score vs Allergen Volume for {allergen_name}")
        axes.set_xlabel("Allergen Volume")
        axes.set_ylabel("Symptom Burden Score")

        plt.tight_layout()

        # --- Save to PNG ---
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:

        logger.error("Error generating plot: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to generate plot")