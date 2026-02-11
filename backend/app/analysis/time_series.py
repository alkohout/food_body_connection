import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import logging
from sqlalchemy.orm import Session
from app.data.analysis_data import (
    get_all_allergen_events_df,
    get_all_symptom_events_df,
)
import traceback
from fastapi import HTTPException
import pandas as pd
from io import BytesIO

logger = logging.getLogger("app/analysis/time_series.py")
logging.basicConfig(level=logging.INFO)

def time_series(
    db: "Session",
    current_user: int,
    allergen_name: str,
    rolling_days: int = 3,
):
    """
    Generate a stacked time series plot showing:

    Top panel:
        - Daily symptom burden (raw values)
        - Rolling mean (smoothed trend)

    Bottom panel:
        - Daily allergen exposure volume (bar chart)

    Parameters
    ----------
    db : Session
        Active database session.
    current_user : int
        ID of the user whose data is analysed.
    allergen_name : str
        Name of allergen to visualise.
    rolling_days : int, optional
        Window size (in days) for rolling average smoothing.
        Default = 3.

    Returns
    -------
    BytesIO
        PNG image buffer containing the generated time series plot.
    """

    try:
        # --------------------------------------------------
        # Load allergen and symptom data
        # --------------------------------------------------
        allergen_events = get_all_allergen_events_df(db, current_user, allergen_name)
        symptom_events = get_all_symptom_events_df(db, current_user)

        # Ensure symptom data exists
        if symptom_events.empty:
            raise ValueError("No symptom data available")

        # Convert timestamps to daily resolution
        symptom_events["days"] = symptom_events["date_time"].dt.floor("D")
        allergen_events["days"] = allergen_events["date_time"].dt.floor("D")

        # --------------------------------------------------
        # Aggregate symptom data per day
        # --------------------------------------------------
        daily_symptoms = (
            symptom_events
            .groupby("days")
            .agg(
                burden=("symptom_intensity", "sum"),        # total daily intensity
                symptom_count=("symptom_id", "count"),      # number of symptoms logged
                mean_severity=("symptom_intensity", "mean") # average intensity
            )
            .reset_index()
        )

        # Create continuous daily date range
        full_days = pd.date_range(
            start=daily_symptoms["days"].min(),
            end=daily_symptoms["days"].max(),
            freq="D",
        )

        # Reindex to ensure missing days appear with zero values
        daily_symptoms = (
            daily_symptoms
            .set_index("days")
            .reindex(full_days, fill_value=0)
            .rename_axis("days")
            .reset_index()
        )

        # --------------------------------------------------
        # Rolling mean smoothing for symptom burden
        # --------------------------------------------------
        daily_symptoms["burden_smooth"] = (
            daily_symptoms["burden"]
            .rolling(rolling_days, min_periods=1)
            .mean()
        )

        # --------------------------------------------------
        # Aggregate allergen exposure per day
        # --------------------------------------------------
        if not allergen_events.empty:
            daily_exposure = (
                allergen_events
                .groupby("days")
                .agg(volume=("volume", "sum"))  # total daily exposure volume
                .reset_index()
            )
        else:
            # Empty dataframe if no exposures logged
            daily_exposure = pd.DataFrame(columns=["days", "volume"])

        # --------------------------------------------------
        # Create stacked subplot layout
        # --------------------------------------------------
        fig, (ax_symptom, ax_exposure) = plt.subplots(
            2,
            1,
            figsize=(12, 7),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},  # top panel larger
        )

        # ------------------------------
        # Top panel: Symptom burden
        # ------------------------------
        # Raw daily burden
        ax_symptom.plot(
            daily_symptoms["days"],
            daily_symptoms["burden"],
            color="gray",
            alpha=0.4,
            linewidth=1,
            label="Daily burden",
        )

        # Smoothed rolling average
        ax_symptom.plot(
            daily_symptoms["days"],
            daily_symptoms["burden_smooth"],
            color="tab:blue",
            linewidth=2.5,
            label=f"{rolling_days}-day average",
        )

        ax_symptom.set_ylabel("Symptom burden")
        ax_symptom.legend(frameon=False)
        ax_symptom.grid(alpha=0.2)

        # Optional visual severity bands
        ax_symptom.axhspan(0, 3, color="green", alpha=0.05)
        ax_symptom.axhspan(3, 6, color="orange", alpha=0.05)
        ax_symptom.axhspan(6, 10, color="red", alpha=0.05)

        # ------------------------------
        # Bottom panel: Allergen exposure
        # ------------------------------
        if not daily_exposure.empty:
            ax_exposure.bar(
                daily_exposure["days"],
                daily_exposure["volume"],
                width=0.8,
                color="tab:orange",
                alpha=0.7,
            )

        ax_exposure.set_ylabel(f"{allergen_name}\nvolume")
        ax_exposure.set_xlabel("Date")
        ax_exposure.grid(alpha=0.2)

        # --------------------------------------------------
        # Final layout adjustments
        # --------------------------------------------------
        fig.suptitle(
            f"Symptom burden and {allergen_name} exposure",
            fontsize=14,
            y=0.97,
        )

        fig.autofmt_xdate()
        plt.tight_layout()

        # --------------------------------------------------
        # Save plot to PNG buffer
        # --------------------------------------------------
        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return buf

    except Exception as e:
        traceback.print_exc()
        logger.exception("Error generating time series plot")
        raise HTTPException(status_code=500, detail=str(e))