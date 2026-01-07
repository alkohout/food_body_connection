     
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
    X = pd.get_dummies(X, columns=["allergen_name"], drop_first=False)

    summary = (
    pd.concat([X, y], axis=1)
    .groupby("allergen_name")
    .agg(
        n_exposures=("symptom_occurred", "count"),
        symptom_rate=("symptom_occurred", "mean"),
    )
    .query("n_exposures >= 5")
    .sort_values("symptom_rate", ascending=False)
    .head(15)
)

    
    plt.figure(figsize=(10, 6))
    sns.heatmap(summary.corr(), annot=True, fmt=".2f", cmap='coolwarm')
    plt.title("Correlation Heatmap")

        # --- Save to PNG ---
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)

    return buf
