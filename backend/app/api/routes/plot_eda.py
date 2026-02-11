# app/api/routes/plot_eda.py
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.models.table_class import User
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
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


def plot_eda(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
    """
    Generate an exploratory data analysis (EDA) plot showing
    symptom rate within 24 hours of allergen exposure.

    The function:
    1. Retrieves all allergen and symptom events.
    2. Counts symptoms occurring within 24h after each exposure.
    3. Aggregates data at the allergen level.
    4. Computes symptom rate per exposure.
    5. Plots the top 10 allergens ranked by symptom rate.
    6. Returns the plot as a PNG streaming response.

    Parameters
    ----------
    current_user : User
        Authenticated user (FastAPI dependency).
    db : Session
        Database session (FastAPI dependency).

    Returns
    -------
    StreamingResponse (image/png)
        PNG image containing the EDA bar plot.
    """

    try: 

        # --------------------------------------------------
        # Fetch allergen and symptom events as DataFrames
        # --------------------------------------------------
        allergen_events = get_all_allergen_events_df(db, current_user.user_id)
        symptom_events = get_all_symptom_events_df(db, current_user.user_id)

        # Ensure sufficient data exists
        if allergen_events.empty or symptom_events.empty:
            raise HTTPException(status_code=400, detail="Not enough data to plot")

        # Ensure datetime dtype (timezone-aware)
        allergen_events["date_time"] = pd.to_datetime(
            allergen_events["date_time"], utc=True
        )
        symptom_events["date_time"] = pd.to_datetime(
            symptom_events["date_time"], utc=True
        )

        rows = []

        # --------------------------------------------------
        # Count symptoms within 24h after each exposure
        # --------------------------------------------------
        for _, a in allergen_events.iterrows():

            window_start = a["date_time"]
            window_end = window_start + pd.Timedelta(hours=24)

            # Count symptoms occurring in window
            symptom_count = symptom_events[
                (symptom_events["date_time"] >= window_start) &
                (symptom_events["date_time"] <= window_end)
            ].shape[0]

            rows.append({
                "allergen": a["allergen_name"],
                "symptom_count": symptom_count,
                "exposures": 1,  # each row represents one exposure
            })

        df = pd.DataFrame(rows)

        # --------------------------------------------------
        # Aggregate data at allergen level
        # --------------------------------------------------
        df = (
            df
            .groupby("allergen", as_index=False)
            .agg(
                total_symptoms=("symptom_count", "sum"),
                total_exposures=("exposures", "sum"),
            )
        )

        # --------------------------------------------------
        # Filter allergens:
        # - Must have at least one symptom recorded
        # - Must have minimum number of exposures
        # --------------------------------------------------
        df = df[df["total_symptoms"] > 0]
        df = df[df["total_exposures"] >= 5]

        # --------------------------------------------------
        # Compute symptom rate per exposure
        # --------------------------------------------------
        df["symptom_rate"] = (
            df["total_symptoms"] / df["total_exposures"]
        )

        # Select top 10 allergens by symptom rate
        df = df.sort_values(
            "symptom_rate",
            ascending=False
        ).head(10)

        # --------------------------------------------------
        # Plot bar chart
        # --------------------------------------------------
        sns.set(style="whitegrid")

        fig, axes = plt.subplots(
            1,
            1,
            figsize=(12, 10),
            gridspec_kw={'height_ratios': [3]}
        )

        sns.barplot(
            data=df,
            x="allergen",
            y="symptom_rate",
            ax=axes
        )

        axes.set_title(
            "Symptom rate within 24h of allergen exposure (top 10)"
        )
        axes.set_xlabel("Allergen")
        axes.set_ylabel("Symptoms per Exposure")

        plt.tight_layout()

        # --------------------------------------------------
        # Save plot to PNG buffer
        # --------------------------------------------------
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:

        # Log detailed error information
        logger.error("Error generating plot: %s", e)
        logger.error(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail="Failed to generate plot"
        )