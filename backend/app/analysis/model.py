     
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

def model_classification(db: 'Session', current_user: int):
    """
    Perform logistic regression, bootstrap ORs, and return plot buffer.
    """
    try:
        # --- Load data ---
        allergen_events = get_all_allergen_events_df(db, current_user)
        symptom_events = get_all_symptom_events_df(db, current_user)
        X, y = get_xy(db, allergen_events, symptom_events)

        # One-hot encode allergens
        X = pd.get_dummies(X["allergen_name"])
        y = y['symptom_occurred']

        # Split for supervised classification
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        unique_classes = np.unique(y_train)
        if len(unique_classes) < 2:
            raise HTTPException(
                status_code=400,
                detail="Not enough class variation to train model (need both symptom and no-symptom cases)."
            )

        # Fit logistic regression
        model = LogisticRegression(penalty='l1', C=1.0, solver='liblinear', max_iter=1000)
        model.fit(X_train, y_train)

        # --- Cross-validation metrics ---
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        auc_scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
        recall_scores = cross_val_score(model, X, y, cv=cv, scoring=make_scorer(recall_score, pos_label=1))

        mean_auc, std_auc = auc_scores.mean(), auc_scores.std()
        mean_recall, std_recall = recall_scores.mean(), recall_scores.std()
        samples = len(y)

        # --- Bootstrap ORs ---
        or_results = bootstrap_or_ci(
            model_cls=LogisticRegression,
            X=X,
            y=y,
            feature_names=X.columns,
            params={"penalty": "l1", "C": 1.0},
            n_boot=500,
            min_occurrences=5
        )

        # --- Plot ---
        plt.figure(figsize=(10, 6))
        plot_df = or_results.copy()
        plot_df["err_lower"] = plot_df["odds_ratio"] - plot_df["ci_lower"]
        plot_df["err_upper"] = plot_df["ci_upper"] - plot_df["odds_ratio"]

        ax = sns.barplot(data=plot_df, x="allergen", y="odds_ratio")
        ax.errorbar(
            x=range(len(plot_df)),
            y=plot_df["odds_ratio"],
            yerr=[plot_df["err_lower"], plot_df["err_upper"]],
            fmt="none",
            ecolor="black",
            elinewidth=1.5,
            capsize=4
        )

        plt.axhline(1.0, linestyle="--", color="red", alpha=0.7)  # no-effect line
        plt.ylabel("Odds Ratio (symptoms within 24h)")
        plt.xlabel("Allergen")
        plt.title("Allergens Most Likely to Trigger Symptoms")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        # Get colors for metrics
        auc_color = get_color(mean_auc, "auc")
        recall_color = get_color(mean_recall, "recall")
        samples_color = get_color(samples, "samples")


        from matplotlib.patches import Circle

        # Coordinates for the top-right corner
        x_text = 0.8
        y_start = 0.95
        y_step = 0.05

        metrics = [
            ("Model Performance:",None,None,None),
            ("ROC AUC", mean_auc, std_auc, get_color(mean_auc, "auc")),
            ("Symptom recall", mean_recall, std_recall, get_color(mean_recall, "recall")),
            ("Samples", samples, None, get_color(samples, "samples"))
        ]

        # Optional background box
        ax.add_patch(
            plt.Rectangle((0.96, 0.92 - len(metrics)*0.05), 0.25, 0.16,
                        transform=ax.transAxes, color='white', alpha=0.9, zorder=1)
        )

        for i, (name, val, std, color) in enumerate(metrics):
            y = y_start - i*y_step
            
            # Draw colored circle
            circle = Circle((x_text, y), 0.008, transform=ax.transAxes, color=color, zorder=2)
            ax.add_patch(circle)
            
            # Add the text next to circle
            if std is not None:
                text = f"{name}: {val:.2f} ± {std:.2f}"
            else:
                text = f"{name}: {val}"
            plt.text(
                x_text + 0.02, y, text,
                transform=ax.transAxes,
                fontsize=10,
                verticalalignment="center",
                horizontalalignment="left",
                zorder=3
            )


        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        return buf

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def get_color(value, metric):
    """
    Return traffic light color based on metric thresholds.
    """
    if metric == "auc":
        if value >= 0.75:
            return "green"
        elif value >= 0.65:
            return "orange"
        else:
            return "red"
    elif metric == "recall":
        if value >= 0.70:
            return "green"
        elif value >= 0.55:
            return "orange"
        else:
            return "red"
    elif metric == "samples":
        if value >= 200:
            return "green"
        elif value >= 75:
            return "orange"
        else:
            return "red"
