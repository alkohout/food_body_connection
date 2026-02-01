
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

    try: 

        # --- Fetch symptom events as DataFrame ---
        symptom_events = get_all_symptom_events_df(db, current_user.user_id)

        if symptom_events.empty:
            raise HTTPException(status_code=400, detail="Not enough data to plot")

        logger.info("Generating symptom group histogram for user_id=%d", current_user.user_id)

        symptom_counts = symptom_events.groupby("symptom_group").size().reset_index(name="count")
        symptom_counts = symptom_counts.sort_values("count", ascending=False)

        sns.set(style="whitegrid")
        fig, ax = plt.subplots(figsize=(10,6))

        sns.barplot(data=symptom_counts, x="symptom_group", y="count", ax=ax, palette="pastel")
        ax.set_title("Symptom Counts by Symptom Group")
        ax.set_xlabel("Symptom Group")
        ax.set_ylabel("Number of Symptoms Logged")
        plt.xticks(rotation=45, ha="right")

        plt.tight_layout()

        # Save to buffer as before
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        logger.error("Error generating symptom group histogram: %s", str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")





