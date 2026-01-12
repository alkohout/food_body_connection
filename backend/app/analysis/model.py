     
from app.models.table_class import User   
from sqlalchemy.orm import Session
from app.schemas.analyse import X,y
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.analysis.get_xy import get_xy
from app.analysis.supervised_classification import supervised_classification, param_optimization, bootstrap_or_ci
from io import BytesIO
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns       
import logging
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import make_scorer, recall_score
from sklearn.linear_model import LogisticRegression

import numpy as np
import traceback 
from fastapi import HTTPException
import pandas as pd
import statsmodels.api as sm

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
        model, roc_auc, recall, samples = supervised_classification(X,y,method='logistic_regression')
        lr_params = {
            'penalty': ['l1'],
            'C': [1, 10, 100]
        }
        best_params = param_optimization(model,lr_params,X_train, y_train, X_test, y_test)
        model,roc_auc,recall,samples = supervised_classification(X,y,method='logistic_regression',params=best_params)
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        auc_scores = cross_val_score(
            model, X, y, cv=cv, scoring="roc_auc"
        )

        recall_scorer = make_scorer(recall_score, pos_label=1)

        recall_scores = cross_val_score(
            model, X, y, cv=cv, scoring=recall_scorer
        )

        mean_auc = auc_scores.mean()
        std_auc = auc_scores.std()
        mean_recall = recall_scores.mean()
        std_recall = recall_scores.std()

        coefs = model.coef_.ravel()

        allergen_importance = pd.DataFrame({
            "allergen": X.columns,
            "coefficient": coefs,
            "odds_ratio": np.exp(coefs)
        }).sort_values("coefficient", ascending=False)

        or_results = bootstrap_or_ci(
            model_cls=LogisticRegression,
            X=X,
            y=y,
            feature_names=X.columns,
            params=best_params,
            n_boot=500
        )


        # Plot
        plt.figure(figsize=(10, 6))
        plot_df = (
            allergen_importance
            .merge(or_results, on="allergen", how="inner")
            .sort_values("odds_ratio", ascending=False)
        )
        plot_df["err_lower"] = plot_df["odds_ratio"] - plot_df["ci_lower"]
        plot_df["err_upper"] = plot_df["ci_upper"] - plot_df["odds_ratio"]

        ax = sns.barplot(
            data=plot_df,
            x="allergen",
            y="odds_ratio"
        )

        ax.errorbar(
            x=range(len(plot_df)),
            y=plot_df["odds_ratio"],
            yerr=[plot_df["err_lower"], plot_df["err_upper"]],
            fmt="none",
            ecolor="black",
            elinewidth=1.5,
            capsize=4
        )

        plt.axhline(1.0, linestyle="--", color="red", alpha=0.7)
        plt.axhline(1.0, linestyle="--")  # no-effect line
        plt.ylabel("Odds Ratio (symptoms within 24h)")
        plt.xlabel("Allergen")
        plt.title("Allergens Most Likely to Trigger Symptoms")
        plt.xticks(rotation=45, ha="right")  # 45 degrees, right-aligned
        plt.tight_layout()

        performance_text = (
            f"Model performance\n"
            f"ROC AUC: {mean_auc:.2f} ± {std_auc:.2f}\n"
            f"Symptom recall: {mean_recall:.2f} ± {std_recall:.2f}\n"
            f"Samples: {samples:.0f}"
        )

        plt.text(
            0.98, 0.98,
            performance_text,
            transform=plt.gca().transAxes,
            fontsize=10,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9)
        )

        # --- Save to PNG ---
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)

        return buf

    except Exception as e:

        traceback.print_exc()   
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
