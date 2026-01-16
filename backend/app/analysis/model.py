     
from app.models.table_class import User   
from sqlalchemy.orm import Session
from app.schemas.analyse import X,y
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.analysis.get_xy import get_xy
from app.analysis.supervised_classification import bootstrap_or_ci
from io import BytesIO
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns       
import logging
from sklearn.metrics import make_scorer, recall_score
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, GridSearchCV, cross_val_score

import numpy as np
import traceback 
from fastapi import HTTPException
import pandas as pd

logger = logging.getLogger("app/analysis/model.py")
logging.basicConfig(level=logging.INFO)

def model_classification(db: 'Session', current_user: int):
    """
    Perform logistic regression, bootstrap ORs, and return plot buffer with 3 subplots (different lag windows).
    """
    try:
        allergen_events = get_all_allergen_events_df(db, current_user)
        symptom_events = get_all_symptom_events_df(db, current_user)
        lag_windows = [(0, 6), (6, 24), (24, 48)]

        base_model = LogisticRegression(solver="liblinear", max_iter=1000)
        param_grid = {"penalty": ["l1", "l2"], "C": [0.1, 1, 10]}

        best_auc = 0
        best_recall = 0
        for lag_window in lag_windows:

            # --- Load data ---
            X, y = get_xy(db, allergen_events, symptom_events, lag_window)

            # One-hot encode allergens
            X = pd.get_dummies(X["allergen_name"])
            y = y['symptom_occurred'].astype(int)

            # Safety check
            if y.nunique() < 2:
                raise HTTPException(
                    status_code=400,
                    detail="Not enough class variation to train model."
                )

            # --- Nested CV ---
            outer_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            inner_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

            # CV for performance metrics
            grid = GridSearchCV(base_model, param_grid, cv=inner_cv, scoring="roc_auc")
            auc_scores = cross_val_score(grid, X, y, cv=outer_cv, scoring="roc_auc")
            recall_scores = cross_val_score(grid, X, y, cv=outer_cv, scoring=make_scorer(recall_score, pos_label=1))
            mean_auc, std_auc = auc_scores.mean(), auc_scores.std()
            mean_recall, std_recall = recall_scores.mean(), recall_scores.std()
            samples = len(y)
            if mean_auc > best_auc:
                best_auc = mean_auc
                best_auc_std = std_auc
                best_recall = mean_recall
                best_recall_std = std_recall
                best_window = lag_window
                best_X = X
                best_y = y
                best_samples =  samples

        # --- Final model for ORs ---
        final_grid = GridSearchCV(
            base_model,
            param_grid,
            cv=5,
            scoring="roc_auc"
        )
        final_grid.fit(best_X, best_y)
        final_model = final_grid.best_estimator_
        best_params = final_grid.best_params_

        or_results = bootstrap_or_ci(
            model_cls=LogisticRegression,
            X=best_X,
            y=best_y,
            feature_names=best_X.columns,
            params={
                "penalty": best_params["penalty"],
                "C": best_params["C"],
                "solver": "liblinear",
                "max_iter": 1000
            },
            n_boot=500,
            min_occurrences=5
        )
        
        # Sort by odds ratio and take top 10 allergens
        top_allergens = or_results.sort_values("odds_ratio", ascending=False)["allergen"].head(10).tolist()

        # --- Plot on the current axis ---
        plot_df = or_results.copy()
        plot_df = or_results.set_index("allergen").reindex(top_allergens).reset_index()
        plot_df["err_lower"] = plot_df["odds_ratio"] - plot_df["ci_lower"]
        plot_df["err_upper"] = plot_df["ci_upper"] - plot_df["odds_ratio"]
        order = top_allergens 

        fig, ax = plt.subplots(figsize=(12, 10))
        sns.barplot(
            data=plot_df,
            x="allergen",
            y="odds_ratio",
            order=order,
            ax=ax
        )

        # Get bar centers from seaborn
        bar_centers = [bar.get_x() + bar.get_width() / 2 for bar in ax.patches]

        ax.errorbar(
            x=bar_centers,
            y=plot_df["odds_ratio"],
            yerr=[
                plot_df["odds_ratio"] - plot_df["ci_lower"],
                plot_df["ci_upper"] - plot_df["odds_ratio"]
            ],
            fmt="none",
            ecolor="black",
            elinewidth=1.5,
            capsize=4,
            zorder=3
        )

        ax.axhline(1.0, linestyle="--", color="red", alpha=0.7)
        ax.set_ylabel("Odds Ratio")
        ax.set_xlabel("Allergen")
        ax.set_title(f"Lag window: {best_window[0]}-{best_window[1]}h")
        ax.tick_params(axis='x', rotation=45)

        # --- Metrics box ---
        from matplotlib.patches import Rectangle
        rect = Rectangle((0.65, 0.75), 0.35, 0.25, transform=ax.transAxes, color="white", alpha=0.85, zorder=2)
        ax.add_patch(rect)

        plt.text(0.67, 0.945, "Model Performance:", transform=ax.transAxes, fontsize=12, color="black", zorder=4)

        auc_color = get_color(best_auc, "auc")
        recall_color = get_color(best_recall, "recall")
        samples_color = get_color(best_samples, "samples")
        metrics = [("ROC AUC", best_auc, best_auc_std, auc_color),
                    ("Symptom recall", best_recall, best_recall_std, recall_color),
                    ("Samples", best_samples, None, samples_color)]
        x_text = 0.95
        y_start = 0.91
        y_step = 0.06
        for i, (name, val, std, color) in enumerate(metrics):
            y = y_start - i * y_step
            text = f"{name}: {val:.2f} ± {std:.2f}" if std is not None else f"{name}: {val}"
            plt.text(x_text, y, text, transform=ax.transAxes, fontsize=12,
                        verticalalignment="top", horizontalalignment="right",
                        color=color, zorder=4)

        # --- Finalize figure ---
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
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
