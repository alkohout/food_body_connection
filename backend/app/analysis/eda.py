     
from app.models.table_class import User   
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.schemas.analyse import X,y
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.analysis.eda import get_xy
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns       

def eda(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    allergen_events = get_all_allergen_events_df(db, current_user.user_id)
    symptom_events = get_all_symptom_events_df(db, current_user.user_id)

    X,y = get_xy(allergen_events, symptom_events)

    df = pd.concat([X, y], axis=1)
    
    plt.figure(figsize=(10, 6))
    sns.heatmap(df.corr(), annot=True, fmt=".2f", cmap='coolwarm')
    plt.title("Correlation Heatmap")

        # --- Save to PNG ---
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return buf
