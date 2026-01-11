     
from app.models.table_class import User   
from sqlalchemy.orm import Session
from app.schemas.analyse import X,y
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.analysis.get_xy import get_xy
from app.analysis.supervised_classification import supervised_classification, param_optimization
from io import BytesIO
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns       
import logging
from sklearn.model_selection import train_test_split
import numpy as np

logger = logging.getLogger("app/analysis/model.py")
logging.basicConfig(level=logging.INFO)

def model_classification(
    db: Session,
    current_user: int
):
    try:

        allergen_events = get_all_allergen_events_df(db, current_user)
        symptom_events = get_all_symptom_events_df(db, current_user)

        X,y = get_xy(db, allergen_events, symptom_events)
        X = pd.get_dummies(X["allergen_name"])
        y = y['symptom_occurred']
        

        X_train,  X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
        model, fpr,tpr,roc_auc = supervised_classification(X,y,method='logistic_regression')
        lr_params = {
            'penalty': ['l1'],
            'C': [1, 10, 100]
        }
        best_params = param_optimization(model,lr_params,X_train, y_train, X_test, y_test)
        model,fpr,tpr,roc_auc = supervised_classification(X,y,method='logistic_regression',params=best_params)

        coefs = model.coef_.ravel()

        allergen_importance = pd.DataFrame({
            "allergen": X.columns,
            "coefficient": coefs,
            "odds_ratio": np.exp(coefs)
        }).sort_values("coefficient", ascending=False)


        # Plot
        plt.figure(figsize=(10, 6))
        plot_df = allergen_importance.sort_values("odds_ratio", ascending=True)
        sns.barplot(
            data=plot_df,
            x="odds_ratio",
            y="allergen"
        )
        plt.axvline(1.0, linestyle="--")  # no-effect line
        plt.xlabel("Odds Ratio (symptoms within 24h)")
        plt.ylabel("Allergen")
        plt.title("Allergens Most Likely to Trigger Symptoms")
        plt.tight_layout()

        # --- Save to PNG ---
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)

        return buf

    except Exception as e:

        traceback.print_exc()   # 🔴 THIS IS CRITICAL
        raise HTTPException(status_code=500, detail=str(e))

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
