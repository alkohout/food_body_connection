def bootstrap_or_ci(model_cls, X, y, feature_names, params=None, n_boot=500, min_occurrences=5):
    """
    Estimate odds ratios (ORs) and 95% confidence intervals using bootstrap
    resampling with logistic regression.

    The function:
    1. Filters out rare features (to prevent unstable / extreme ORs).
    2. Repeatedly resamples the dataset with replacement.
    3. Fits a logistic regression model on each bootstrap sample.
    4. Stores exponentiated coefficients (odds ratios).
    5. Computes mean OR and percentile-based 95% confidence intervals.

    Parameters
    ----------
    model_cls : class
        Model class (e.g., LogisticRegression).
    X : pd.DataFrame
        Feature matrix (one-hot encoded allergens).
    y : pd.Series
        Binary target variable (symptom occurrence).
    feature_names : list
        Original list of feature names.
    params : dict, optional
        Model hyperparameters.
    n_boot : int
        Number of bootstrap resamples (default = 500).
    min_occurrences : int
        Minimum number of times a feature must appear
        to be included in analysis.

    Returns
    -------
    pd.DataFrame
        DataFrame with:
        - allergen
        - odds_ratio (mean bootstrap OR)
        - ci_lower (2.5th percentile)
        - ci_upper (97.5th percentile)
    """

    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import make_scorer, recall_score
    import numpy as np
    import pandas as pd

    # Store bootstrap OR values for each feature
    ors = {f: [] for f in feature_names}

    # Use empty dict if no parameters provided
    params = params or {}

    # --------------------------------------------------
    # Filter rare allergens to avoid unstable OR estimates
    # --------------------------------------------------
    mask = X.sum(axis=0) >= min_occurrences
    feature_names_filtered = X.columns[mask]
    X = X[feature_names_filtered]

    # --------------------------------------------------
    # Bootstrap resampling loop
    # --------------------------------------------------
    for _ in range(n_boot):

        # Sample indices with replacement
        idx = np.random.choice(len(X), len(X), replace=True)
        X_b = X.iloc[idx]
        y_b = y.iloc[idx]

        # Choose solver depending on penalty type
        solver = 'liblinear' if params.get('penalty') == 'l1' else 'lbfgs'

        # Remove conflicting solver key if present
        params_copy = params.copy()
        params_copy.pop('solver', None)

        # Fit logistic regression on bootstrap sample
        model = model_cls(**params_copy, solver=solver)
        model.fit(X_b, y_b)

        # Store exponentiated coefficients (odds ratios)
        for f, coef in zip(feature_names_filtered, model.coef_[0]):
            ors[f].append(np.exp(coef))

    # --------------------------------------------------
    # Aggregate bootstrap results into summary DataFrame
    # --------------------------------------------------
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

    # --------------------------------------------------
    # Optional: clip extremely large ORs for readability
    # --------------------------------------------------
    results_df["odds_ratio"] = results_df["odds_ratio"].clip(0, 20)

    # Sort allergens by descending odds ratio
    results_df = results_df.sort_values(
        "odds_ratio",
        ascending=False
    ).reset_index(drop=True)

    return results_df