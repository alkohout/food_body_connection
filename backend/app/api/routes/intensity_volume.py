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
            end = start + timedelta(hours=lag_end)
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

        # Scatter
        sns.scatterplot(data=df, x="volume", y="burden_score", ax=ax, alpha=0.6)


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

        # --- Predict probabilities for plotting ---
        X_range = pd.DataFrame({"volume": np.linspace(df["volume"].min(), df["volume"].max(), 200)})
        probs = res.predict(X_range)

        # Reverse cumulative probabilities (probability >= level)
        cum_probs = np.flip(np.cumsum(np.flip(probs, axis=1), axis=1))

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

        # --- Title ---
        ax.text(
            0.67, 0.945,
            "Dose–Response Confidence:",
            transform=ax.transAxes,
            fontsize=12,
            color="black",
            zorder=4
        )

        # --- Metrics text ---
        #metrics = [
        #    ("Signal (pseudo R²)", pseudo_r2, r2_color, f"{pseudo_r2:.2f}"),
        #    ("Curve stability (EDOF)", edof, edof_color, f"{edof:.1f}"),
        #    ("Samples", samples, samples_color, f"{samples}"),
        #]
#
#        y_start = 0.91
#        y_step = 0.04
#
#        for i, (name, _, color, text_val) in enumerate(metrics):
#            ax.text(
#                0.95,
#                y_start - i * y_step,
#                f"{name}: {text_val}",
#                transform=ax.transAxes,
#                fontsize=12,
#                verticalalignment="top",
#                horizontalalignment="right",
#                color=color,
#                zorder=3
#            )

        # Plot 
        fig, ax = plt.subplots(figsize=(12, 8))

        labels = [
            "Any symptoms (≥ mild)",
            "Moderate or worse",
            "Severe"
        ]

        for i, label in enumerate(labels, start=1):
            ax.plot(
                X_range,
                cum_probs[:, i],
                linewidth=2,
                label=label
            )

        ax.set_ylim(0, 1)
        ax.set_xlabel("Allergen volume")
        ax.set_ylabel("Predicted probability")
        ax.set_title("Probability of symptom severity vs allergen volume")

        ax.legend()
        ax.grid(True)

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

def get_color(value, metric):
    if metric == "pseudo_r2":
        if value >= 0.30:
            return "green"
        elif value >= 0.15:
            return "orange"
        else:
            return "red"
    elif metric == "edof":
        if value <= 5:
            return "green"
        elif value <= 8:
            return "orange"
        else:
            return "red"
    elif metric == "samples":
        if value >= 40:
            return "green"
        elif value >= 15:
            return "orange"
        else:
            return "red"
