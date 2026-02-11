
def bootstrap_or_ci(model_cls, X, y, feature_names, params=None, n_boot=500, min_occurrences=5):
    """
    Bootstrap logistic regression to compute odds ratios and confidence intervals.
    Filters rare features to avoid exploding ORs.
    """
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import make_scorer, recall_score
    import numpy as np
    import pandas as pd

    ors = {f: [] for f in feature_names}
    params = params or {}

    # Filter rare allergens
    mask = X.sum(axis=0) >= min_occurrences
    feature_names_filtered = X.columns[mask]
    X = X[feature_names_filtered]

    for _ in range(n_boot):
        idx = np.random.choice(len(X), len(X), replace=True)
        X_b = X.iloc[idx]
        y_b = y.iloc[idx]

        solver = 'liblinear' if params.get('penalty') == 'l1' else 'lbfgs'
        # Remove conflicting solver key
        params_copy = params.copy()
        params_copy.pop('solver', None)

        model = model_cls(**params_copy, solver=solver)
        model.fit(X_b, y_b)

        for f, coef in zip(feature_names_filtered, model.coef_[0]):
            ors[f].append(np.exp(coef))

    results_df = pd.DataFrame([
        {
            "allergen": f,
            "odds_ratio": np.mean(values) if len(values) > 0 else np.nan,
            "ci_lower": np.percentile(values, 2.5) if len(values) > 0 else np.nan,
            "ci_upper": np.percentile(values, 97.5) if len(values) > 0 else np.nan
        }
        for f, values in ors.items()
        if len(values) > 0
    ])

    # Optional: clip ORs for readability
    results_df["odds_ratio"] = results_df["odds_ratio"].clip(0, 20)
    results_df = results_df.sort_values("odds_ratio", ascending=False).reset_index(drop=True)

    return results_df