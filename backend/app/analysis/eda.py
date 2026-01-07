     
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

logger = logging.getLogger("app/analysis/eda.py")
logging.basicConfig(level=logging.INFO)

def eda_plot_heatmap(
    db: Session,
    current_user: int
):

    allergen_events = get_all_allergen_events_df(db, current_user)
    symptom_events = get_all_symptom_events_df(db, current_user)

    X,y = get_xy(db, allergen_events, symptom_events)
    df = pd.concat([X, y], axis=1)
    agg = (
        df
        .groupby("allergen_name")
        .agg(
            n_exposures=("symptom_occurred", "size"),
            symptom_rate=("symptom_occurred", "mean"),
            mean_intensity=("symptom_max_intensity", "mean"),
        )
    )
    # Convert categorical variables to 0/1
    X_encoded = pd.get_dummies(df["allergen_name"])
    X_encoded = pd.concat([X_encoded, X['exposure_volume'] ])
   
    # Combine into one DataFrame
    df_corr = pd.concat([X_encoded, y], axis=1)

    # Compute correlation matrix
    #corr_matrix = df_corr.corr()

    # For multiple symptoms:
    corr_matrix = pd.concat([X_encoded, y], axis=1).corr().loc[X_encoded.columns, y.columns]

    plt.figure(figsize=(10, 6))
    sns.heatmap(corr_matrix, annot=False, cmap="coolwarm",center=0)
    #agg = agg.sort_values("n_exposures", ascending=False).head(20)
    #sns.heatmap(
    #    agg[["symptom_rate", "mean_intensity"]],
    #    annot=True,
    #    cmap="coolwarm",
    #)
    plt.title("Allergen-Symptom Correlation")

        # --- Save to PNG ---
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)

    return buf
