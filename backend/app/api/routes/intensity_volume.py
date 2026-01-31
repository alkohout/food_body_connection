# app/api/routes/intensity_volume.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.database import get_db
from app.models.table_class import User
from app.data.analysis_data import get_all_symptom_events_df, get_all_allergen_events_df
from datetime import timedelta
import pandas as pd
import seaborn as sns
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
import logging
import traceback
import numpy as np
from statsmodels.miscmodels.ordinal_model import OrderedModel

logger = logging.getLogger("backend/app/api/routes/intensity_volume.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get('/intensity_volume')
def intensity_volume(
    allergen_name: str,
    lag_start: int = 0,
    lag_end: int = 6,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    try: 
        # --- Fetch allergen and symptom events ---
        allergen_df = get_all_allergen_events_df(db, current_user.user_id, allergen_name=allergen_name)
        symptom_df = get_all_symptom_events_df(db, current_user.user_id)

        if allergen_df.empty:
            logger.warning("No allergen events found")
            return None  # or empty plot

        allergen_df["date_time"] = pd.to_datetime(allergen_df["date_time"], utc=True)
        symptom_df["date_time"] = pd.to_datetime(symptom_df["date_time"], utc=True)
        symptom_df = symptom_df.sort_values("date_time")

        # --- Compute burden score per allergen event ---
        rows = []
        for _, allergen in allergen_df.iterrows():
            start = allergen["date_time"] + timedelta(hours=lag_start)
            end = allergen["date_time"] + timedelta(hours=lag_end)
            window_symptoms = symptom_df[(symptom_df["date_time"] >= start) & (symptom_df["date_time"] <= end)]
            peak_intensity = window_symptoms["symptom_intensity"].max()
            if pd.isna(peak_intensity):
                peak_intensity = 0
            burden_score = peak_intensity
            rows.append({
                "volume": allergen["volume"],
                "burden_score": burden_score,
            })
        df = pd.DataFrame(rows)

        if df.empty:
            logger.warning("No valid rows for plot")
            return None

        # --- Plot scatter + GAM ---
        sns.set(style="whitegrid")
        fig, ax = plt.subplots(figsize=(12, 10))
        print("Volume range min/max:", df["volume"].min(), df["volume"].max())

        # --- Prepare data ---
        df["volume"] = df["volume"].astype(float)
        df["burden_score"] = df["burden_score"].astype(int)  # ordinal levels

        X = df[["volume"]]  # keep as DataFrame
        y = df["burden_score"]

        # --- Fit ordered model ---
        model = OrderedModel(y, X, distr="logit")
        res = model.fit(method="bfgs", disp=False)

        # --- Odds ratio + CI ---
        idx = res.model.exog_names.index("volume")
        beta = res.params[idx]
        se = res.bse[idx]

        or_value = np.exp(beta)
        ci_low = np.exp(beta - 1.96*se)
        ci_high = np.exp(beta + 1.96*se)

        # Plot
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.violinplot(x="burden_score", y="volume", data=df, cut=0, inner="quartile")
        #sns.boxplot(data=df, x="burden_score", y="volume", palette="pastel")
        #sns.swarmplot(data=df, x="burden_score", y="volume", color="black", alpha=0.5)
        plt.xlabel(f"Peak symptom intensity within {lag_start} - {lag_end} hrs after {allergen_name} exposure")
        plt.ylabel(f"Volume of {allergen_name} exposure")
        plt.title("Effect of Allergen Volume on Peak Symptom Intensity")
        plt.show()

        from matplotlib.patches import Rectangle

        # --- Rectangle background ---
        rect = Rectangle(
            (0.65, 0.75),
            0.35, 0.25,
            transform=ax.transAxes,
            color="white",
            alpha=0.8,
            zorder=2
        )
        ax.add_patch(rect)

        # --- Metrics text ---
        metrics = [
             ("Odds Ratio (volume)", or_value, or_color(or_value, ci_low, ci_high), f"{or_value:.2f} [{ci_low:.2f}, {ci_high:.2f}]"),
        ]

        y_start = 0.945
        y_step = 0.04

        for i, (name, _, color, text_val) in enumerate(metrics):
            ax.text(
                0.95,
                y_start - i * y_step,
                f"{name}: {text_val}",
                transform=ax.transAxes,
                fontsize=12,
                verticalalignment="top",
                horizontalalignment="right",
                color=color,
                zorder=3
            )

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

def or_color(or_val, ci_low, ci_high):
    """
    Determine color for odds ratio based on significance and effect size.
    
    Green: CI excludes 1 → statistically significant.
    Orange: CI barely includes 1 → borderline significance.
    Red: CI includes 1 with wide range or unexpected effect direction.
    """
    # Statistically significant and OR > 1 (risk increases)
    if ci_low > 1:
        return "green"
    # Statistically significant and OR < 1 (protective effect)
    elif ci_high < 1:
        return "green"
    # CI includes 1 but mostly >1 or <1 (borderline)
    elif (ci_low <= 1 <= ci_high) and ((ci_high - ci_low)/ci_low < 1.0):
        return "orange"
    # CI includes 1 with wide uncertainty or OR around 1 → weak evidence
    else:
        return "red"
