# app/api/routes/plot_eda.py
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.models.table_class import User
from app.data.analysis_data import get_all_allergen_events, get_all_symptom_events, get_allergen
from datetime import timedelta, datetime
import traceback

from io import BytesIO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

logger = logging.getLogger("app/api/routes/plot_eda.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/plot_eda")
def plot_eda(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):

    try: 

        # --- Fetch events as DataFrames ---
        allergen_events = get_all_allergen_events_df(db, current_user.user_id)
        symptom_events = get_all_symptom_events_df(db, current_user.user_id)

        if allergen_events.empty or symptom_events.empty:
            raise HTTPException(status_code=400, detail="Not enough data to plot")

        # Ensure datetime dtype
        allergen_events["date_time"] = pd.to_datetime(allergen_events["date_time"], utc=True)
        symptom_events["date_time"] = pd.to_datetime(symptom_events["date_time"], utc=True)

        rows = []

        # --- Per-exposure symptom counting ---
        for _, a in allergen_events.iterrows():
            window_start = a["date_time"]
            window_end = window_start + pd.Timedelta(hours=24)

            symptom_count = symptom_events[
                (symptom_events["date_time"] >= window_start) &
                (symptom_events["date_time"] <= window_end)
            ].shape[0]

            rows.append({
                "allergen": a["allergen_name"],   # see note below if missing
                "symptom_count": symptom_count,
                "exposures": 1,
            })

        df = pd.DataFrame(rows)

        # --- Aggregate to allergen level ---
        df = (
            df
            .groupby("allergen", as_index=False)
            .agg(
                total_symptoms=("symptom_count", "sum"),
                total_exposures=("exposures", "sum"),
            )
        )

        # --- Compute rate ---
        df["symptom_rate"] = df["total_symptoms"] / df["total_exposures"]

        # Optional cleanup
        df = df[df["total_symptoms"] > 0]

        # Top 10 by rate
        df = df.sort_values("symptom_rate", ascending=False).head(10)
 
        # --- Plotting ---
        sns.set(style="whitegrid")
        fig, axes = plt.subplots(1, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3]})
        # Sort by count descending and take top 10
        df = df.sort_values("symptom_rate", ascending=False).head(10)
        sns.barplot(data=df, x="allergen", y="symptom_rate", ax=axes)
        axes.set_title(f"Symptom rate within 24h of allergen exposure (top 10)")
        axes.set_xlabel("Allergen")
        axes.set_ylabel("Symptoms per Exposure")

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
