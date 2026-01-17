     
from app.models.table_class import User   
from sqlalchemy.orm import Session
from app.schemas.analyse import X,y
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.analysis.get_xy import get_xy
from io import BytesIO
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns       
import logging
import traceback
from fastapi import HTTPException

WINDOWS = [
            ("0-6h", 0, 6),
            ("6-24h", 6, 24),
            ("24-48h", 24, 48),
]
WINDOW_ORDER = ["none", "0-6h", "6-24h", "24-48h"]
WINDOW_LABELS = {
    "none": "No allergen",
    "0-6h": "0–6 h",
    "6-24h": "6–24 h",
    "24-48h": "24–48 h",
}


logger = logging.getLogger("app/analysis/eda.py")
logging.basicConfig(level=logging.INFO)

def eda_plot_heatmap(
    db: Session,
    current_user: int
):

    allergen_events = get_all_allergen_events_df(db, current_user)
    symptom_events = get_all_symptom_events_df(db, current_user)

    X,y = get_xy(db, allergen_events, symptom_events, lag_window = (6,24))

    # One-hot encode allergens only
    X_encoded = pd.get_dummies(X["allergen_name"])

    # Use the symptom DataFrame as-is (no get_dummies)
    df_corr = pd.concat([X_encoded, y], axis=1)

    # Compute correlations between allergens and symptoms
    corr_matrix = df_corr.corr().loc[X_encoded.columns, y.columns]

    # Optional: sort allergens by max absolute correlation to symptoms
    corr_matrix = corr_matrix.loc[corr_matrix.abs().max(axis=1).sort_values(ascending=False).index,
                                corr_matrix.abs().max(axis=0).sort_values(ascending=False).index]

    # Plot
    plt.figure(figsize=(12, 8))
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="coolwarm", center=0, linewidths=0.5)
    plt.title("Allergen-Symptom Correlation (Sorted by Strength)")
    plt.ylabel("Allergens")
    plt.xlabel("Symptoms")
    plt.tight_layout()

    # --- Save to PNG ---
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)

    return buf

    # agg = (
    #    df
    #    .groupby("allergen_name")
    #    .agg(
    #        n_exposures=("symptom_occurred", "size"),
    #        symptom_rate=("symptom_occurred", "mean"),
    #        mean_intensity=("symptom_max_intensity", "mean"),
    #    )
    #agg = agg.sort_values("n_exposures", ascending=False).head(20)
    #sns.heatmap(
    #    agg[["symptom_rate", "mean_intensity"]],
    #    annot=True,
    #    cmap="coolwarm",
    #)

def bar_percentages(
    db: "Session",
    current_user: int,
    allergen_name: str,
):
    """
    """

    try:
        # --------------------------------------------------
        # Load data
        # --------------------------------------------------
        allergen_events = get_all_allergen_events_df(db, current_user, allergen_name)
        symptom_events = get_all_symptom_events_df(db, current_user)

        if symptom_events.empty:
            raise ValueError("No symptom data available")


        analysis_df = build_daily_analysis_table(
            symptom_events,
            allergen_events
        )

        bar_summary = summarise_for_bars(analysis_df)

        print(bar_summary.sort_values(["symptom_group", "exposure_window"]))

        fig = plot_symptom_risk_bars(bar_summary)

        # --------------------------------------------------
        # Output buffer
        # --------------------------------------------------
        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    except Exception as e:
        traceback.print_exc()
        logger.exception("Error generating bar plot")
        raise HTTPException(status_code=500, detail=str(e))

def build_daily_symptoms(symptom_events: pd.DataFrame) -> pd.DataFrame:
    """
    Returns:
    date | symptom_group | symptom_present (0/1)
    """
    df = symptom_events.copy()
    df["date"] = df["date_time"].dt.floor("D")

    daily = (
        df.groupby(["date", "symptom_group"])
          .agg(symptom_present=("symptom_intensity", lambda x: (x > 0).any()))
          .reset_index()
    )

    daily["symptom_present"] = daily["symptom_present"].astype(int)
    return daily

from datetime import timedelta

def assign_exposure_window(
    day_start: pd.Timestamp,
    allergen_times: pd.Series
) -> str:
    """
    Given the start of a day and allergen event times,
    return the closest matching exposure window.
    """

    deltas = (day_start - allergen_times).dt.total_seconds() / 3600
    deltas = deltas[deltas >= 0]  # only past exposures

    if deltas.empty:
        return "none"

    min_delta = deltas.min()

    for label, lo, hi in WINDOWS:
        if lo <= min_delta < hi:
            return label

    return "none"

def build_daily_allergen_exposure(
    allergen_events: pd.DataFrame,
    date_index: pd.DatetimeIndex
) -> pd.DataFrame:
    """
    Returns:
    date | exposure_window
    """
    allergen_times = allergen_events["date_time"]

    rows = []
    for day in date_index:
        window = assign_exposure_window(day, allergen_times)
        rows.append({
            "date": day,
            "exposure_window": window
        })

    return pd.DataFrame(rows)

def build_daily_analysis_table(
    symptom_events: pd.DataFrame,
    allergen_events: pd.DataFrame
) -> pd.DataFrame:

    daily_symptoms = build_daily_symptoms(symptom_events)

    all_days = pd.date_range(
        start=daily_symptoms["date"].min(),
        end=daily_symptoms["date"].max(),
        freq="D",
        tz=daily_symptoms["date"].dt.tz
    )

    daily_exposure = build_daily_allergen_exposure(
        allergen_events,
        all_days
    )

    df = daily_symptoms.merge(
        daily_exposure,
        on="date",
        how="left"
    )

    df["exposure_window"] = df["exposure_window"].fillna("none")
    return df

def summarise_for_bars(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns:
    symptom_group | exposure_window | symptom_rate | n_days
    """
    summary = (
        df.groupby(["symptom_group", "exposure_window"])
          .agg(
              symptom_rate=("symptom_present", "mean"),
              n_days=("symptom_present", "count")
          )
          .reset_index()
    )

    return summary


def plot_symptom_risk_bars(bar_summary: pd.DataFrame):
    """
    bar_summary columns:
    - symptom_group
    - exposure_window
    - symptom_rate (0–1)
    - n_days
    """

    symptom_groups = sorted(bar_summary["symptom_group"].unique())
    n_groups = len(symptom_groups)

    fig, axes = plt.subplots(
        nrows=n_groups,
        ncols=1,
        figsize=(7, 3 * n_groups),
        sharey=True
    )

    if n_groups == 1:
        axes = [axes]

    for ax, group in zip(axes, symptom_groups):
        df = bar_summary[bar_summary["symptom_group"] == group]

        # Ensure all windows exist
        df = (
            pd.DataFrame({"exposure_window": WINDOW_ORDER})
            .merge(df, on="exposure_window", how="left")
        )

        rates = df["symptom_rate"].fillna(0) * 100
        counts = df["n_days"].fillna(0)

        bars = ax.bar(
            range(len(WINDOW_ORDER)),
            rates
        )

        # Annotate bars
        for bar, rate, n in zip(bars, rates, counts):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{rate:.0f}%\n(n={int(n)})",
                ha="center",
                va="bottom",
                fontsize=9
            )

        ax.set_title(group)
        ax.set_xticks(range(len(WINDOW_ORDER)))
        ax.set_xticklabels([WINDOW_LABELS[w] for w in WINDOW_ORDER])
        ax.set_ylabel("Days with symptoms (%)")
        ax.set_ylim(0, 100)

        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Symptom risk by allergen exposure window", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    return fig
