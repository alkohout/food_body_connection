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

# GAM import
from pygam import LinearGAM, s

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
            start = allergen["date_time"]
            end = start + timedelta(hours=24)
            window_symptoms = symptom_df[(symptom_df["date_time"] >= start) & (symptom_df["date_time"] <= end)]
            total_intensity = window_symptoms["symptom_intensity"].fillna(0).sum()
            burden_score = total_intensity
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

        # Fit GAM
        X = df["volume"].values.reshape(-1, 1)
        y = df["burden_score"].values

        lams = np.logspace(-3, 3, 10)

        if len(df) < 10:
            gam = LinearGAM(
                s(0, n_splines=5),
                lam=10
            ).fit(X, y)
        else:
            gam = LinearGAM(
                s(0, n_splines=10)
            ).gridsearch(X, y, lam=lams)

        X_range = np.linspace(df["volume"].min(), df["volume"].max(), 200).reshape(-1, 1)  # smooth X
        y_pred = gam.predict(X_range)
        y_conf = gam.confidence_intervals(X_range)

        from matplotlib.patches import Rectangle

        # --- Metrics ---
        stats = gam.statistics_
        pseudo_r2 = stats["pseudo_r2"].get("explained_deviance", 0.0)
        edof = stats.get("edof", 0.0)
        samples = len(df)

        r2_color = get_color(pseudo_r2, "pseudo_r2")
        edof_color = get_color(edof, "edof")
        samples_color = get_color(samples, "samples")

        confidence_pct = compute_confidence(pseudo_r2, edof, samples)
        confidence_color = (
            "green" if confidence_pct >= 70 else
            "orange" if confidence_pct >= 40 else
            "red"
        )

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
        metrics = [
            ("Signal (pseudo R²)", pseudo_r2, r2_color, f"{pseudo_r2:.2f}"),
            ("Curve stability (EDOF)", edof, edof_color, f"{edof:.1f}"),
            ("Samples", samples, samples_color, f"{samples}"),
            ("Overall confidence", confidence_pct, confidence_color, f"{confidence_pct}%"),
        ]

        y_start = 0.91
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

        # Plot GAM fit and confidence interval
        ax.plot(X_range, y_pred, color="red", linewidth=2, label="GAM fit")
        ax.fill_between(X_range.flatten(), y_conf[:,0], y_conf[:,1], color="red", alpha=0.2, label="95% CI")

        ax.set_title(f"Symptom Burden vs Allergen Volume for {allergen_name}")
        ax.set_xlabel("Allergen Volume (gm)")
        ax.set_ylabel("Symptom Burden Score")
        ax.legend()

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

def compute_confidence(pseudo_r2, edof, samples):
    scores = []

    scores.append(1.0 if pseudo_r2 >= 0.30 else 0.5 if pseudo_r2 >= 0.15 else 0.2)
    scores.append(1.0 if edof <= 5 else 0.6 if edof <= 8 else 0.3)
    scores.append(1.0 if samples >= 40 else 0.6 if samples >= 15 else 0.3)

    return int(100 * np.mean(scores))
