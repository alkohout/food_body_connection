     
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
from sklearn.model_selection import StratifiedKFold, GridSearchCV, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import make_scorer, recall_score

import numpy as np
import traceback 
from fastapi import HTTPException
import pandas as pd
import statsmodels.api as sm

logger = logging.getLogger("app/analysis/model.py")
logging.basicConfig(level=logging.INFO)

def model_classification(db: 'Session', current_user: int):
    """
    Perform logistic regression, bootstrap ORs, and return a single plot buffer
    showing all three lag windows in one plot with different colors.
    """
    try:
        allergen_events = get_all_allergen_events_df(db, current_user)
        symptom_events = get_all_symptom_events_df(db, current_user)
        lag_windows = [(0, 6), (6, 24), (24, 48)]
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]  # Blue, Orange, Green
        all_plot_dfs = []

        for lag_window, color in zip(lag_windows, colors):
            X, y = get_xy(db, allergen_events, symptom_events, lag_window)
            X = pd.get_dummies(X["allergen_name"])
            y = y['symptom_occurred'].astype(int)

            if y.nunique() < 2:
                continue  # Skip lag window if not enough class variation

            # Fit final model for ORs
            base_model = LogisticRegression(solver="liblinear", max_iter=1000)
            param_grid = {"penalty": ["l1", "l2"], "C": [0.1, 1, 10]}
            final_grid = GridSearchCV(base_model, param_grid, cv=5, scoring="roc_auc")
            final_grid.fit(X, y)
            best_params = final_grid.best_params_

            or_results = bootstrap_or_ci(
                model_cls=LogisticRegression,
                X=X,
                y=y,
                feature_names=X.columns,
                params={
                    "penalty": best_params["penalty"],
                    "C": best_params["C"],
                    "solver": "liblinear",
                    "max_iter": 1000
                },
                n_boot=500,
                min_occurrences=5
            )
            or_results["lag_window"] = f"{lag_window[0]}-{lag_window[1]}h"
            or_results["color"] = color
            all_plot_dfs.append(or_results)

        if not all_plot_dfs:
            raise HTTPException(status_code=400, detail="Not enough data to plot.")

        # Combine all lag windows
        plot_df = pd.concat(all_plot_dfs, ignore_index=True)

        # Compute error bars
        plot_df["err_lower"] = plot_df["odds_ratio"] - plot_df["ci_lower"]
        plot_df["err_upper"] = plot_df["ci_upper"] - plot_df["odds_ratio"]

        # Sort allergens alphabetically
        allergens = sorted(plot_df["allergen"].unique())
        x = np.arange(len(allergens))
        width = 0.25  # width of bars

        fig, ax = plt.subplots(figsize=(24, 10))

        for i, lag_window in enumerate(lag_windows):
            lw_label = f"{lag_window[0]}-{lag_window[1]}h"
            lw_df = plot_df[plot_df["lag_window"] == lw_label]
            lw_df = lw_df.set_index("allergen").reindex(allergens).reset_index()
            ax.bar(
                x + i * width,
                lw_df["odds_ratio"],
                width=width,
                color=lw_df["color"],
                label=lw_label,
                yerr=[lw_df["err_lower"], lw_df["err_upper"]],
                capsize=4,
                edgecolor="black"
            )

        ax.axhline(1.0, linestyle="--", color="red", alpha=0.7)
        ax.set_xticks(x + width)
        ax.set_xticklabels(allergens, rotation=45, ha="right")
        ax.set_ylabel("Odds Ratio (symptoms)")
        ax.set_xlabel("Allergen")
        ax.set_title("Allergen Odds Ratios by Lag Window")
        ax.legend(title="Lag Window")

        fig.tight_layout()
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
