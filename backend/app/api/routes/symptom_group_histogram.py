
# app/api/routes/symptom_group_histogram.py

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.models.table_class import User
from app.data.analysis_data import get_all_symptom_events_df
from datetime import timedelta, datetime
import traceback

from io import BytesIO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

logger = logging.getLogger("app/api/routes/symptom_group_histogram.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/symptom_group_histogram")
def symptom_group_histogram(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
    """
    Generate a histogram showing the number of logged symptoms
    grouped by symptom category.

    The endpoint:
    1. Retrieves all symptom events for the authenticated user.
    2. Aggregates counts by `symptom_group`.
    3. Displays results as a bar chart.
    4. Returns the plot as a PNG streaming response.
    5. If no symptom data exists, returns a blank image with a message.

    Parameters
    ----------
    current_user : User
        Authenticated user (FastAPI dependency).
    db : Session
        Database session (FastAPI dependency).

    Returns
    -------
    StreamingResponse (image/png)
        PNG image containing the symptom group histogram.
    """

    try: 

        # --------------------------------------------------
        # Fetch symptom events as DataFrame
        # --------------------------------------------------
        symptom_events = get_all_symptom_events_df(db, current_user.user_id)

        # --------------------------------------------------
        # Handle case where no symptom data exists
        # --------------------------------------------------
        if symptom_events.empty:
           if symptom_events.empty:
                # Return a blank image instead of error
                fig, ax = plt.subplots(figsize=(6,4))
                ax.text(0.5, 0.5, "No symptom data available",
                        ha="center", va="center")
                ax.set_axis_off()

                buf = BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight")
                plt.close(fig)
                buf.seek(0)

                return StreamingResponse(buf, media_type="image/png") 

        # --------------------------------------------------
        # Log histogram generation
        # --------------------------------------------------
        logger.info("Generating symptom group histogram for user_id=%d", current_user.user_id)

        # --------------------------------------------------
        # Aggregate symptom counts by group
        # --------------------------------------------------
        symptom_counts = symptom_events.groupby("symptom_group").size().reset_index(name="count")
        symptom_counts = symptom_counts.sort_values("count", ascending=False)

        # --------------------------------------------------
        # Create bar plot
        # --------------------------------------------------
        sns.set(style="whitegrid")
        fig, ax = plt.subplots(figsize=(10,6))

        sns.barplot(data=symptom_counts, x="symptom_group", y="count", ax=ax, palette="pastel")
        ax.set_title("Symptom Counts by Symptom Group")
        ax.set_xlabel("Symptom Group")
        ax.set_ylabel("Number of Symptoms Logged")
        plt.xticks(rotation=45, ha="right")

        plt.tight_layout()

        # --------------------------------------------------
        # Save figure to in-memory buffer
        # --------------------------------------------------
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        # Return PNG image as streaming response
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:

        # --------------------------------------------------
        # Log full error details for debugging
        # --------------------------------------------------
        logger.error("Error generating symptom group histogram: %s", str(e))
        traceback.print_exc()

        # Return generic server error to client
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )





