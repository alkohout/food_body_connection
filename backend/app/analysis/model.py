     
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
from sklearn.metrics import pairwise_distances

import numpy as np
import traceback 
from fastapi import HTTPException
import pandas as pd

logger = logging.getLogger("app/analysis/model.py")
logging.basicConfig(level=logging.INFO)

def model_classification(db: 'Session', current_user: int, return_type="buf"):
    """
    Perform logistic regression, bootstrap ORs, and return plot buffer with 3 subplots (different lag windows).
    """
    try:
        allergen_events = get_all_allergen_events_df(db, current_user)
        symptom_events = get_all_symptom_events_df(db, current_user)
        if allergen_events.empty or symptom_events.empty:

            summary = (
                "Not enough data to perform analysis. Please log more allergen and symptom events to see potential patterns."
            )
            return summary

        lag_windows = [(0, 6), (6, 24), (24, 48)]
        symptom_counts = symptom_events.groupby("symptom_group").size().reset_index(name="count")
        symptom_counts = symptom_counts.sort_values("count", ascending=False)
        top_symptom_group = symptom_counts.iloc[0]["symptom_group"].lower()

        base_model = LogisticRegression(solver="liblinear", max_iter=1000)

        best_auc = 0
        best_recall = 0
        fs = 14 # figure fontsize
        for lag_window in lag_windows:

            # --- Load data ---
            X, y = get_xy(db, current_user, allergen_events, symptom_events, lag_window)

            # One-hot encode allergens
            X = pd.get_dummies(X["allergen_name"])
            y = y['symptom_occurred'].astype(int)

            # Safety check
            if y.nunique() < 2:
                raise HTTPException(
                    status_code=400,
                    detail="Not enough class variation to train model."
                )
            pos_rate = y.mean()
            use_balanced = pos_rate < 0.25 or pos_rate > 0.75
            param_grid = {"penalty": ["l1", "l2"], "C": [0.1, 1, 10],"class_weight": ["balanced"] if use_balanced else [None]}
            
            # --- Collinearity check: Jaccard similarity for boolean allergens ---
            allergen_cols = X.columns.tolist()
            X_bool = X.astype(bool).to_numpy()
            jaccard_dist = pairwise_distances(X_bool.T, metric="jaccard")
            jaccard_sim = 1 - jaccard_dist
            jaccard_df = pd.DataFrame(
                jaccard_sim,
                index=allergen_cols,
                columns=allergen_cols
            )
            # Remove self-similarity
            np.fill_diagonal(jaccard_df.values, 0)
            # Extract strongly co-occurring pairs
            strong_pairs = (
                jaccard_df
                .stack()
                .reset_index()
                .rename(columns={
                    "level_0": "allergen_a",
                    "level_1": "allergen_b",
                    0: "jaccard"
                })
                .query("jaccard > 0.7")
            )

            # Deduplicate A–B vs B–A
            strong_pairs = strong_pairs[
                strong_pairs["allergen_a"] < strong_pairs["allergen_b"]
            ]

            if len(strong_pairs) > 0:
                pair_strings = (
                    strong_pairs
                    .apply(
                        lambda r: f"{r['allergen_a'].lower()}–{r['allergen_b'].lower()}",
                        axis=1
                    )
                    .tolist()
                )

                strong_pairs_text = "We checked for allergens which are often logged together and found co-occurring allergens:\n" + ", ".join(pair_strings)
                strong_col_text = "strong co-occurrence detected"
                strong_col_colour = "red"

            else:
                strong_pairs_text = ""
                strong_col_text = "no strong co-occurrence detected"
                strong_col_colour = "green"

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
                best_use_balanced = "balanced" if use_balanced else None

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
                "max_iter": 1000,
                "class_weight": best_use_balanced
            },
            n_boot=500,
            min_occurrences=5
        )
        
        # Sort by odds ratio and take top 10 allergens
        top_allergens = or_results.sort_values("odds_ratio", ascending=False)["allergen"].head(10).tolist()
        bottom_allergens = or_results.sort_values("odds_ratio", ascending=True)["allergen"].head(10).tolist()

        # --- Plot on the current axis ---

        fig, (ax_top, ax_bot) = plt.subplots(
            2,
            1,
            figsize=(12, 10),
        )
        plt.subplots_adjust(hspace=0.4)

        # top allergens 
        plot_df = or_results.copy()
        plot_df = or_results.set_index("allergen").reindex(top_allergens).reset_index()
        plot_df["err_lower"] = plot_df["odds_ratio"] - plot_df["ci_lower"]
        plot_df["err_upper"] = plot_df["ci_upper"] - plot_df["odds_ratio"]
        order = top_allergens 
        sns.barplot(
            data=plot_df,
            x="allergen",
            y="odds_ratio",
            order=order,
            ax=ax_top
        )
        sig_top_allergens = plot_df[plot_df["ci_lower"] > 1]
        sig_bot_allergens = plot_df[plot_df["ci_upper"] < 1]


        # Get bar centers from seaborn
        bar_centers = [bar.get_x() + bar.get_width() / 2 for bar in ax_top.patches]

        ax_top.errorbar(
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

        ax_top.axhline(1.0, linestyle="--", color="red", alpha=0.7)
        ax_top.set_ylabel("Odds Ratio", fontsize=fs)
        ax_top.set_xlabel("Allergen", fontsize=14 )
        ax_top.set_title(f"Lag window: {best_window[0]}-{best_window[1]}h", fontsize=14)
        ax_top.tick_params(axis='x', rotation=45)

        # --- Metrics box ---
        from matplotlib.patches import Rectangle

        rect = Rectangle((0.65, 0.65), 0.35, 0.25, transform=ax_top.transAxes, color="white", alpha=0.85, zorder=2)
        ax_top.add_patch(rect)

        plt.text(0.67, 0.945, "Model Performance:", transform=ax_top.transAxes, fontsize=12, color="black", zorder=4)

        auc_colour = get_colour(best_auc, "auc")
        recall_colour = get_colour(best_recall, "recall")
        samples_colour = get_colour(best_samples, "samples")
        metrics = [("ROC AUC", best_auc, best_auc_std, auc_colour),
                    ("Symptom recall", best_recall, best_recall_std, recall_colour),
                    ("Samples", best_samples, None, samples_colour)]
        x_text = 0.95
        y_start = 0.91
        y_step = 0.06
        for i, (name, val, std, colour) in enumerate(metrics):
            y = y_start - i * y_step
            text = f"{name}: {val:.2f} ± {std:.2f}" if std is not None else f"{name}: {val}"
            plt.text(x_text, y, text, transform=ax_top.transAxes, fontsize=12,
                        verticalalignment="top", horizontalalignment="right",
                        color=colour, zorder=4)
        plt.text(
            x_text,
            y - y_step,
            strong_col_text,
            transform=ax_top.transAxes,
            fontsize=10,
            verticalalignment="top",
            horizontalalignment="right",
            color=strong_col_colour,
            zorder=4,
            wrap=True
        )

        # metrics_summary
        metric_lights = {
            "ROC AUC": auc_colour,
            "Recall": recall_colour,
            "Sample Size": samples_colour,
            "Colinearity": strong_col_colour,
        }

        # bottom allergens 
        plot_df = or_results.copy()
        plot_df = or_results.set_index("allergen").reindex(bottom_allergens).reset_index()
        plot_df["err_lower"] = plot_df["odds_ratio"] - plot_df["ci_lower"]
        plot_df["err_upper"] = plot_df["ci_upper"] - plot_df["odds_ratio"]
        order = bottom_allergens 
        sns.barplot(
            data=plot_df,
            x="allergen",
            y="odds_ratio",
            order=order,
            ax=ax_bot
        )

        # Get bar centers from seaborn
        bar_centers = [bar.get_x() + bar.get_width() / 2 for bar in ax_bot.patches]

        ax_bot.errorbar(
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

        ax_bot.axhline(1.0, linestyle="--", color="red", alpha=0.7)
        ax_bot.set_ylabel("Odds Ratio", fontsize=fs)
        ax_bot.set_xlabel("Allergen", fontsize=14 )
        ax_bot.tick_params(axis='x', rotation=45)

        if return_type=="buf":
            buf = BytesIO()
            plt.savefig(buf, format="png", bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)
            return buf

        elif return_type=="text":
            plt.close(fig)
            top_allergens = sig_top_allergens["allergen"].tolist()
            bot_allergens = sig_bot_allergens["allergen"].tolist()

            top_text = allergen_list_text(top_allergens)
            bot_text = allergen_list_text(bot_allergens)

            summary = (
                f"Analysis using a logistic regression model{' with class weighting to adjust for imbalance' if use_balanced else ''} suggests {top_text} are associated with a higher likelihood of symptoms. "
                f"The most commonly reported symptoms were {top_symptom_group}. "
                f"{overall_reliability_text(metric_lights)}"
                f"{strong_pairs_text}"
            )

            return summary 

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def get_colour(value, metric):
    """
    Return traffic light colour based on metric thresholds.
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

def allergen_list_text(allergens):

    allergens = [a.lower() for a in allergens]

    if len(allergens) == 0:
        return "none"
    if len(allergens) == 1:
        return allergens[0]
    if len(allergens) == 2:
        return " and ".join(allergens)
    return ", ".join(allergens[:-1]) + f", and {allergens[-1]}"

def worst_light(lights):
    """Return the worst (most concerning) light present."""
    if "red" in lights:
        return "red"
    if "orange" in lights:
        return "orange"
    return "green"

def metric_summary_text(metric_name, light):
    METRIC_TEXT = {
        "green": "performed well and showed strong discrimination",
        "orange": "showed moderate performance with some uncertainty",
        "red": "performed poorly and showed limited discriminatory ability",
    }
    return f"{metric_name} {METRIC_TEXT[light]}."

def overall_reliability_text(metric_lights: dict):
    """
    metric_lights example:
    {
        "ROC AUC": "green",
        "Calibration": "orange",
        "Stability": "green",
        "Sample Size": "red"
    }
    """
    lights = list(metric_lights.values())
    worst = worst_light(lights)

    if worst == "green":
        return (
            "Overall, the logistic regression model performed well across all evaluation metrics. "
            "The results are considered reliable and suitable for identifying potential patterns. "
        )

    if worst == "orange":
        return (
            "Overall, the logistic regression model showed mixed performance across evaluation metrics. "
            "The results should be interpreted with some caution, particularly for borderline findings. "
        )

    return (
        "Overall, the logistic regression model showed weak performance on at least one key metric. "
        "The results are considered unreliable and should be interpreted with caution, "
        "as observed patterns may reflect noise rather than true associations. "
    )
