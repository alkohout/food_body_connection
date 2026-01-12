     
from app.models.table_class import User   
from sqlalchemy.orm import Session
from app.schemas.analyse import X,y
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.analysis.get_xy import get_xy
from app.analysis.supervised_classification import supervised_classification, param_optimization, bootstrap_or_ci
from io import BytesIO
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns       
import logging
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import make_scorer, recall_score
from sklearn.linear_model import LogisticRegression

import numpy as np
import traceback 
from fastapi import HTTPException
import pandas as pd
import statsmodels.api as sm

logger = logging.getLogger("app/analysis/time_series.py")
logging.basicConfig(level=logging.INFO)

def time_series(db: 'Session', current_user: int, allergen_name: str):
    """
    Basic time series plot.
    """
    try:
        # --- Load data ---
        allergen_events = get_all_allergen_events_df(db, current_user, allergen_name)
        symptom_events = get_all_symptom_events_df(db, current_user)

        symptom_events["days"] = symptom_events["date_time"].dt.floor("D")

        daily_symptoms = (
            symptom_events
            .groupby("date_time")
            .agg(
                symptom_count=("symptom_id", "count"),
                mean_severity=("symptom_intensity", "mean")
            )
            .reset_index()
        )

        allergen_events["days"] = allergen_events["date_time"].dt.floor("D")

        exposure_days = allergen_events["days"].unique()


        # --- Plot ---
        plt.figure(figsize=(10, 6))

        # symptom time series
        plt.plot(
            daily_symptoms["days"],
            daily_symptoms["symptom_count"],
            label="Symptoms",
            linewidth=2
        )

        # allergen exposures
        for d in exposure_days:
            plt.axvline(d, linestyle="--", alpha=0.3)

        plt.title(f"Symptoms over time with {allergen_name} exposure")
        plt.xlabel("Date")
        plt.ylabel("Symptom count")
        plt.legend()
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        return buf

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
