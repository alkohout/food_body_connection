     
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

logger = logging.getLogger("app/analysis/eda.py")
logging.basicConfig(level=logging.INFO)

def eda_plot_heatmap(
    db: Session,
    current_user: int
):

    allergen_events = get_all_allergen_events_df(db, current_user)
    symptom_events = get_all_symptom_events_df(db, current_user)

    X,y = get_xy(db, current_user, allergen_events, symptom_events, lag_window = (6,24))

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
