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

        # --- Fetch allergen and symptom events for user ---
        allergen_events = get_all_allergen_events(db, current_user.user_id)
        symptom_events = get_all_symptom_events(db, current_user.user_id)
        
        # --- Determine overall min/max dates ---
        allergen_times = [a.date_time for a in allergen_events]
        symptom_times = [s.date_time for s in symptom_events]

        # Combine and take min/max
        all_times = allergen_times + symptom_times
        if all_times:  # make sure there is data
            start_dt = min(all_times)
            end_dt = max(all_times)
        else:
            # fallback if no data
            start_dt = end_dt = datetime.now()


        logger.info("Generating EDA plot for user_id=%d", current_user.user_id)
        logger.info("Start date: %s, End date: %s", start_dt, end_dt)   
        logger.info("Allergen events: %d, Symptom events: %d", len(allergen_events), len(symptom_events))

        rows = []
        for a in allergen_events:
            window_end = a.date_time + timedelta(hours=24)
            
            # Count symptoms in the 24h window
            count = sum(1 for s in symptom_events if a.date_time <= s.date_time <= window_end)
            allergen_obj = get_allergen(db, allergen_id=a.allergen_id)
            
            # Append a row
            rows.append({
                "allergen_name": allergen_obj.allergen_name if allergen_obj else "Unknown",
                "symptom_count_24h": count
            })

        # Convert to DataFrame
        df = pd.DataFrame(rows)
        df = df.groupby(["allergen_name"])["symptom_count_24h"].sum().reset_index()

        # --- Plotting ---
        sns.set(style="whitegrid")
        fig, axes = plt.subplots(1, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3]})

        # Remove allergens with 0 count
        rows = rows[rows["symptom_count_24h"] > 0]

        # Sort by count descending and take top 10
        top10 = rows.sort_values("symptom_count_24h", ascending=False).head(10)
        sns.barplot(data=top10, x="Allergen", y="Count", ax=axes)
        axes.set_title(f"Number of symptoms within 24h of allergen exposures (top 10 allergens)")
        axes.set_xlabel("Allergen")
        axes.set_ylabel("Symptom Count")

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
