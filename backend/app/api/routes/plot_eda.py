# app/api/routes/plot_eda.py
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from collections import defaultdict
from fastapi.responses import StreamingResponse
from app.models.table_class import User
from app.data.analysis_data import get_allergen, get_all_allergen_events, get_all_symptom_events
from datetime import timedelta
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

        # --- Fetch allergen and symptom events for user ---
        allergen_events = get_all_allergen_events(db, current_user.user_id)
        symptom_events = get_all_symptom_events(db, current_user.user_id)
        
        # --- Determine overall min/max dates ---
        start_dt = min(allergen_events.date_time, symptom_events.date_time)
        end_dt = max(allergen_events.date_time, symptom_events.date_time)

        logger.info("Generating EDA plot for user_id=%d", current_user.user_id)
        logger.info("Start date: %s, End date: %s", start_dt, end_dt)   
        logger.info("Allergen events: %d, Symptom events: %d", len(allergen_events), len(symptom_events))

        # --- Time series: count of symptom events within 24h of each allergen ---
        counts_by_allergen = defaultdict(int)
        for a in allergen_events:
            window_end = a.date_time + timedelta(hours=24)
            count = sum(1 for s in symptom_events if a.date_time <= s.date_time <= window_end)
            counts_by_allergen[a.allergen_id] += count

        # --- Map allergen IDs to names for plotting ---
        allergen_ids = list(counts_by_allergen.keys())
        allergen_names = get_allergen(db, current_user.user_id, allergen_ids=allergen_ids)
        logger.info("Allergen names mapping: %s", allergen_names)

        # --- Plotting ---
        sns.set(style="whitegrid")
        fig, axes = plt.subplots(1, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3]})

        # Convert counts to DataFrame for barplot
        bar_data = pd.DataFrame({
            "Allergen": [allergen_names[a_id] for a_id in counts_by_allergen.keys()],
            "Count": [counts_by_allergen[a_id] for a_id in counts_by_allergen.keys()]
        })

        # Remove allergens with 0 count
        bar_data = bar_data[bar_data["Count"] > 0]

        # Sort by count descending and take top 10
        bar_data_top10 = bar_data.sort_values("Count", ascending=False).head(10)
        sns.barplot(data=bar_data_top10, x="Allergen", y="Count", ax=axes)
        axes.set_title(f"Number of symptoms within 24h of allergen exposures (top 10 allergens)")
        axes.set_xlabel("Allergen")
        axes.set_ylabel("Symptom Count")

        plt.tight_layout()

        # --- Save to PNG ---
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        # logging for debugging
        logger.info("Number of allergen events: %d", len(allergen_events))
        logger.info("Number of symptom events: %d", len(symptom_events))
        logger.info("Counts by allergen: %s", counts_by_allergen)

        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:

        logger.error("Error generating plot: %s", e)
        logger.error(traceback.format_exc())
        # Optionally return a 500 with a message
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to generate plot")
