     
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

WINDOW_ORDER = ["not_exposed", "exposed_0_6h", "exposed_6_24h", "exposed_24_48h"]
WINDOW_LABELS = {
    "not_exposed": "No allergen",
    "exposed_0_6h": "0–6 h",
    "exposed_6_24h": "6–24 h",
    "exposed_24_48h": "24–48 h",
}

def plot_percentages(
    db: "Session",
    current_user: int,
    allergen_name: str,
):
    """
    Plots exposure percentages for each symptom group as subplots.
    """
    try:
        allergen_events = get_all_allergen_events_df(db, current_user, allergen_name)
        symptom_events = get_all_symptom_events_df(db, current_user)

        if symptom_events.empty:
            raise ValueError("No symptom data available")

        exposure_df = build_symptom_allergen_exposure_df(symptom_events, allergen_events)

        symptom_groups = exposure_df["symptom_group"].unique()
        n_groups = len(symptom_groups)

        fig, axes = plt.subplots(nrows=n_groups, ncols=1, figsize=(7, 3*n_groups), sharey=True)
        if n_groups == 1:
            axes = [axes]

        for ax, group in zip(axes, symptom_groups):
            df_group = exposure_df[exposure_df["symptom_group"] == group]

            # Compute percentages and counts
            summary = df_group[WINDOW_ORDER].agg(['sum', 'count']).T
            summary['percent'] = 100 * summary['sum'] / summary['count']

            # Ensure all windows present
            summary = summary.reindex(WINDOW_ORDER)

            bars = ax.bar(range(len(WINDOW_ORDER)), summary['percent'], color="skyblue")

            # Annotate bars with percentage and n
            for i, (bar, pct, n) in enumerate(zip(bars, summary['percent'], summary['count'])):
                ax.text(
                    bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 1,
                    f"{pct:.0f}%\n(n={int(n)})",
                    ha="center",
                    va="bottom",
                    fontsize=9
                )

            ax.set_xticks(range(len(WINDOW_ORDER)))
            ax.set_xticklabels([WINDOW_LABELS[w] for w in WINDOW_ORDER])
            ax.set_ylabel("Percentage of symptoms")
            ax.set_title(f"{group} symptoms")
            ax.set_ylim(0, 100)
            ax.grid(axis="y", alpha=0.3)

        fig.suptitle(f"Symptom percentages by allergen exposure ({allergen_name})", fontsize=14)
        fig.tight_layout(rect=[0, 0, 1, 0.96])

        # Output buffer
        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    except Exception as e:
        traceback.print_exc()
        logger.exception("Error generating bar plot")
        raise HTTPException(status_code=500, detail=str(e))

def build_symptom_allergen_exposure_df(
    symptom_df: pd.DataFrame,
    allergen_df: pd.DataFrame
) -> pd.DataFrame:
    """
    symptom_df: output of get_all_symptom_events_df
    allergen_df: output of get_all_allergen_events_df (already filtered to one allergen)
    """

    # Ensure datetime + sorted
    symptom_df = symptom_df.copy()
    allergen_df = allergen_df.copy()

    symptom_df["date_time"] = pd.to_datetime(symptom_df["date_time"], utc=True)
    allergen_df["date_time"] = pd.to_datetime(allergen_df["date_time"], utc=True)

    allergen_times = allergen_df["date_time"].sort_values().values

    # Prepare exposure columns
    symptom_df["exposed_0_6h"] = 0
    symptom_df["exposed_6_24h"] = 0
    symptom_df["exposed_24_48h"] = 0

    for idx, symptom_time in symptom_df["date_time"].items():
        # Compute time differences (symptom - allergen)
        deltas = symptom_time - allergen_df["date_time"]

        # Only look at exposures before symptom
        deltas = deltas[deltas >= pd.Timedelta(0)]

        if ((deltas <= pd.Timedelta(hours=6))).any():
            symptom_df.at[idx, "exposed_0_6h"] = 1

        elif ((deltas > pd.Timedelta(hours=6)) & (deltas <= pd.Timedelta(hours=24))).any():
            symptom_df.at[idx, "exposed_6_24h"] = 1

        elif ((deltas > pd.Timedelta(hours=24)) & (deltas <= pd.Timedelta(hours=48))).any():
            symptom_df.at[idx, "exposed_24_48h"] = 1

    # Not exposed = none of the above
    symptom_df["not_exposed"] = (
        (symptom_df[["exposed_0_6h", "exposed_6_24h", "exposed_24_48h"]].sum(axis=1) == 0)
        .astype(int)
    )

    return symptom_df
