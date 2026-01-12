import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import logging
from sqlalchemy.orm import Session
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
import traceback 
from fastapi import HTTPException
import pandas as pd
from io import BytesIO

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

        # Floor to days
        symptom_events["days"] = symptom_events["date_time"].dt.floor("D")
        allergen_events["days"] = allergen_events["date_time"].dt.floor("D")

        # --- Aggregate symptoms per day ---
        daily_symptoms = (
            symptom_events
            .groupby("days")
            .agg(
                burden=("symptom_intensity", "sum"),
                symptom_count=("symptom_id", "count"),
                mean_severity=("symptom_intensity", "mean")
            )
            .reset_index()
        )

        # --- Ensure continuous date range ---
        full_days = pd.date_range(
            start=daily_symptoms["days"].min(),
            end=daily_symptoms["days"].max(),
            freq="D"
        )

        daily_symptoms = (
            daily_symptoms
            .set_index("days")
            .reindex(full_days, fill_value=0)
            .rename_axis("days")
            .reset_index()
        )
        
        exposure_days = allergen_events["days"].unique()

        volumes = allergen_events["volume"].astype(float)

        # scale marker sizes (tweak 50–500 as needed)
        marker_sizes = 50 + 450 * (volumes / volumes.max())


        # --- Plot ---
        fig, ax = plt.subplots(figsize=(10, 6))
        ax2 = ax.twinx()

        # Symptom burden (left axis)
        ax.plot(
            daily_symptoms["days"],
            daily_symptoms["burden"],
            label="Symptom burden",
            linewidth=2,
            color="tab:blue"
)

        # Exposure timing lines
        for d in exposure_days:
            ax.axvline(d, linestyle="--", alpha=0.2)

        # Exposure volumes (right axis)
        volumes = allergen_events["volume"].astype(float)
        marker_sizes = 50 + 450 * (volumes / volumes.max())

        ax2.scatter(
            allergen_events["days"],
            volumes,
            s=marker_sizes,
            alpha=0.6,
            color="tab:orange",
            label="Exposure volume"
        )

        # Labels & titles
        ax.set_title(f"Symptoms over time with {allergen_name} exposure")
        ax.set_xlabel("Date")
        ax.set_ylabel("Symptom burden")
        ax2.set_ylabel("Allergen volume")

        ax.tick_params(axis="x", rotation=45)

        # Combined legend
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="upper left")

        fig.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        buf.seek(0)
        return buf

    except Exception as e:
        traceback.print_exc()
        logger.exception("Error generating time series plot")
        raise HTTPException(status_code=500, detail=str(e))
