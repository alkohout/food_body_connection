import pandas as pd
import numpy as np
from statsmodels.stats.multitest import multipletests

def temporal_stats_rate(
    allergen_events: pd.DataFrame,
    symptom_events: pd.DataFrame,
    pre_hours: int = 24,
    post_hours: int = 24,
    n_permutations: int = 1000
):
    """
    Returns a DataFrame of symptom groups with rate-based pre/post comparison,
    permutation p-value, and FDR correction.
    """
    results = []

    # Ensure timestamps are sorted
    allergen_events = allergen_events.sort_values("date_time")
    symptom_events = symptom_events.sort_values("date_time")

    symptom_groups = symptom_events["symptom_group"].unique()

    for symptom in symptom_groups:
        symptom_ts = symptom_events[symptom_events["symptom_group"] == symptom]["date_time"]

        # Pre/post rates per allergen event
        pre_rates, post_rates = [], []

        for t in allergen_events["date_time"]:
            pre_window = ((symptom_ts >= t - pd.Timedelta(hours=pre_hours)) &
                          (symptom_ts < t))
            post_window = ((symptom_ts > t) &
                           (symptom_ts <= t + pd.Timedelta(hours=post_hours)))
            
            pre_rates.append(pre_window.sum() / pre_hours)
            post_rates.append(post_window.sum() / post_hours)

        pre_rates = np.array(pre_rates)
        post_rates = np.array(post_rates)

        # Skip symptom groups with too few events
        if len(pre_rates) < 5 or (pre_rates.sum() + post_rates.sum()) == 0:
            continue

        # Observed difference in means
        obs_diff = post_rates.mean() - pre_rates.mean()

        # Permutation test
        combined = np.concatenate([pre_rates, post_rates])
        perm_diffs = []
        for _ in range(n_permutations):
            np.random.shuffle(combined)
            perm_pre = combined[:len(pre_rates)]
            perm_post = combined[len(pre_rates):]
            perm_diffs.append(perm_post.mean() - perm_pre.mean())
        perm_diffs = np.array(perm_diffs)
        p_value = (np.abs(perm_diffs) >= np.abs(obs_diff)).mean()

        p_value = float(p_value) if p_value is not None else np.nan

        results.append({
            "symptom_group": symptom,
            "pre_rate": pre_rates.mean(),
            "post_rate": post_rates.mean(),
            "rate_diff": obs_diff,
            "p_value": p_value,
        })

    # Convert to DataFrame
    results_df = pd.DataFrame(results)

    # Drop rows with missing p-values
    results_df = results_df.dropna(subset=["p_value"])

    # Multiple testing correction
    if not results_df.empty:
        results_df["q_value"] = multipletests(results_df["p_value"], method="fdr_bh")[1]
        # Sort by q_value
        results_df = results_df.sort_values("q_value").reset_index(drop=True)

    return results_df


