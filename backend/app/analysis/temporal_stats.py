# backend/app/analysis/temporal_stats.py

import numpy as np
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.table_class import User
from datetime import timedelta
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
import pandas as pd
import logging
from scipy.stats import binomtest
import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import fisher_exact
from io import BytesIO

def plot_stats(
    db: Session,
    current_user: int,
    allergen_name: str,
    lag_start: int,
    lag_end: int,
    symptom_group: str
    ):

    """
    Generate a bar chart summarising the temporal relationship
    between allergen exposure and symptom occurrence.

    The function calculates:
    1. The percentage of exposure-days followed by symptoms
       within a specified lag window.
    2. The percentage of symptom-days preceded by exposure
       within the same lag window.

    Parameters
    ----------
    db : Session
        Active database session.
    current_user : int
        ID of the user whose data is analysed.
    allergen_name : str
        Name of the allergen to analyse.
    lag_start : int
        Start of lag window in hours.
    lag_end : int
        End of lag window in hours.
    symptom_group : str
        Symptom category being evaluated.

    Returns
    -------
    BytesIO
        PNG image buffer containing the generated bar chart.
    """

    # --------------------------------------------------
    # Create matplotlib figure
    # --------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 10))

    # --------------------------------------------------
    # Retrieve daily exposure and symptom indicators
    # --------------------------------------------------
    # days       -> index of days analysed
    # exposures  -> binary indicator per day (exposure occurred)
    # symptoms   -> binary indicator per day (symptom occurred)
    days, exposures, symptoms = days_df(
        db,
        current_user,
        allergen_name=allergen_name,
        symptom_group=symptom_group,
        lag_start=lag_start,
        lag_end=lag_end
    ) 

    # --------------------------------------------------
    # Calculate percentages
    # --------------------------------------------------
    # Percentage of exposure-days followed by symptoms
    e_perc = 100 * exposures.sum() / len(exposures)

    # Percentage of symptom-days preceded by exposure
    s_perc = 100 * symptoms.sum() / len(symptoms)

    # Labels for the two bars
    labels = [
        f'Exposure-days followed by symptoms (within {lag_start} - {lag_end} hrs)',
        f'Symptom-days preceded by exposure (within {lag_start} - {lag_end} hrs)'
    ]

    heights = [e_perc, s_perc] 

    # --------------------------------------------------
    # Create bar chart
    # --------------------------------------------------
    ax.bar(labels, heights)

    # Set chart title to symptom group
    ax.set_title(symptom_group)

    # Y-axis label
    ax.set_ylabel("Percent")

    # Add slight headroom above tallest bar
    ax.set_ylim(0, max(heights) * 1.1)

    # Improve spacing/layout
    plt.tight_layout()

    # --------------------------------------------------
    # Output image buffer
    # --------------------------------------------------
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return buf

def get_pvalue_colour(p):
    """
    Determine a traffic-light colour based on statistical significance.

    Colour thresholds:
    - Green  : Highly statistically significant (p < 0.01)
    - Orange : Statistically significant at conventional level (p < 0.05)
    - Red    : Not statistically significant (p >= 0.05)

    Parameters
    ----------
    p : float
        P-value from a statistical test.

    Returns
    -------
    str
        Traffic-light colour representing strength of evidence:
        "green", "orange", or "red".
    """

    # Highly significant result (strong evidence against null hypothesis)
    if p < 0.01:
        return "green"

    # Statistically significant at 5% level (moderate evidence)
    elif p < 0.05:
        return "orange"

    # Not statistically significant (weak or no evidence)
    else:
        return "red"

def plot_stats_risk(
    db: Session,
    current_user: int,
    allergen_name: str,
    lag_start: int,
    lag_end: int,
    symptom_group: str
):

    """
    Generate a bar chart comparing symptom risk on exposed vs unexposed days.

    The function:
    1. Splits days into exposed and unexposed groups.
    2. Calculates the probability of symptoms in each group.
    3. Computes the absolute risk difference.
    4. Performs Fisher's Exact Test for statistical significance.
    5. Displays results with traffic-light colouring for the p-value.

    Parameters
    ----------
    db : Session
        Active database session.
    current_user : int
        ID of the user whose data is analysed.
    allergen_name : str
        Name of the allergen being evaluated.
    lag_start : int
        Start of lag window in hours.
    lag_end : int
        End of lag window in hours.
    symptom_group : str
        Symptom category being analysed.

    Returns
    -------
    BytesIO
        PNG image buffer containing the generated risk comparison plot.
    """

    # --------------------------------------------------
    # Create figure
    # --------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 10))

    # --------------------------------------------------
    # Retrieve daily exposure and symptom indicators
    # --------------------------------------------------
    days, exposures, symptoms = days_df(
        db,
        current_user,
        allergen_name=allergen_name,
        symptom_group=symptom_group,
        lag_start=lag_start,
        lag_end=lag_end
    )

    # --------------------------------------------------
    # Split dataset into exposed vs unexposed days
    # --------------------------------------------------
    exposed_days = days[days["exposed"] == 1]
    unexposed_days = days[days["exposed"] == 0]

    # --------------------------------------------------
    # Calculate symptom risk (probability) in each group
    # --------------------------------------------------
    # Probability of symptom on exposed days
    risk_exposed = exposed_days["any_symptom"].mean()

    # Probability of symptom on unexposed days (baseline)
    risk_unexposed = unexposed_days["any_symptom"].mean()

    # Convert to percentages for plotting
    risks = [100 * risk_unexposed, 100 * risk_exposed]
    labels = ["No exposure (baseline)", f"Exposure to {allergen_name}"]

    # --------------------------------------------------
    # Plot bar chart
    # --------------------------------------------------
    ax.bar(labels, risks)
    ax.set_ylabel("Percent of days with symptoms")
    ax.set_ylim(0, max(risks) * 1.25)  # Add visual headroom

    # --------------------------------------------------
    # Calculate absolute risk difference
    # --------------------------------------------------
    risk_diff = 100 * (risk_exposed - risk_unexposed)

    # --------------------------------------------------
    # Fisher's Exact Test (2x2 contingency table)
    # --------------------------------------------------
    table = [
        [
            exposed_days["any_symptom"].sum(),
            exposed_days.shape[0] - exposed_days["any_symptom"].sum()
        ],
        [
            unexposed_days["any_symptom"].sum(),
            unexposed_days.shape[0] - unexposed_days["any_symptom"].sum()
        ]
    ]

    # Compute p-value
    _, p_value = fisher_exact(table)

    # --------------------------------------------------
    # Annotate p-value and risk difference
    # --------------------------------------------------
    p_color = get_pvalue_colour(p_value)  # Traffic-light colour
    r_color = 'black'

    x_text = 0.95
    y_start = 0.95
    y = y_start 

    # Display p-value (top-right)
    text = f"p-value: {p_value:.3f}" 
    plt.text(
        x_text, y, text,
        transform=ax.transAxes,
        fontsize=12,
        verticalalignment="top",
        horizontalalignment="right",
        color=p_color,
        zorder=4
    )

    # Display absolute risk difference below p-value
    ax.text(
        x_text,
        y - .05,
        f"Absolute risk difference: {risk_diff:+.1f}%",
        transform=ax.transAxes,
        fontsize=12,
        verticalalignment="top",
        horizontalalignment="right",
        color=r_color,
        zorder=3
    )

    # --------------------------------------------------
    # Add white background box behind annotation text
    # --------------------------------------------------
    from matplotlib.patches import Rectangle
    rect = Rectangle(
        (0.7, 0.8), 0.3, 0.2,
        transform=ax.transAxes,
        color="white",
        alpha=0.85,
        zorder=2
    )
    ax.add_patch(rect)

    # --------------------------------------------------
    # Set plot title
    # --------------------------------------------------
    ax.set_title(
        f"{symptom_group}\nSymptoms within {lag_start}–{lag_end} hours",
        fontsize=16
    )

    plt.tight_layout()

    # --------------------------------------------------
    # Save plot to PNG buffer
    # --------------------------------------------------
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return buf

def days_df(
    db: Session,
    current_user: User,
    allergen_name: str,
    symptom_group: str,
    lag_start: int,
    lag_end: int
):

    """
    Construct daily-level exposure and symptom indicators for a given
    allergen and symptom group within a specified lag window.

    The function:
    1. Extracts allergen and symptom events.
    2. Determines whether symptoms occurred within a time window after exposure.
    3. Determines whether exposure occurred within a time window prior to symptoms.
    4. Aggregates data to daily level.
    5. Returns a complete daily time series including days with no events.

    Parameters
    ----------
    db : Session
        Active database session.
    current_user : User
        User whose data is analysed.
    allergen_name : str
        Name of allergen to evaluate.
    symptom_group : str
        Symptom category to evaluate.
    lag_start : int
        Start of lag window (hours).
    lag_end : int
        End of lag window (hours).

    Returns
    -------
    days_df : pd.DataFrame
        Daily dataframe with:
        - date
        - any_symptom (0/1)
        - exposed (0/1)
    daily_exposure : pd.Series
        Whether exposure-day was followed by symptom within lag window.
    daily_symptoms : pd.Series
        Whether symptom-day had prior exposure within lag window.
    """

    # --------------------------------------------------
    # Extract allergen events for selected allergen
    # --------------------------------------------------
    allergen_events = get_all_allergen_events_df(
        db, current_user, allergen_name=allergen_name
    )

    # --------------------------------------------------
    # Extract symptom events for selected symptom group
    # --------------------------------------------------
    symptom_events = get_all_symptom_events_df(
        db, current_user, symptom_group=symptom_group
    )

    # --------------------------------------------------
    # Ensure timestamps are timezone-aware and sorted
    # --------------------------------------------------
    allergen_events["date_time"] = pd.to_datetime(
        allergen_events["date_time"], utc=True
    )
    allergen_events = allergen_events.sort_values("date_time")

    symptom_events["date_time"] = pd.to_datetime(
        symptom_events["date_time"], utc=True
    )
    symptom_events = symptom_events.sort_values("date_time")

    # --------------------------------------------------
    # Determine if symptom occurred within lag window AFTER exposure
    # --------------------------------------------------
    allergen_events["symptom"] = allergen_events["date_time"].apply(
        lambda t: symptom_within_window(symptom_events, t, lag_start, lag_end)
    )

    # Extract date only (remove time component)
    allergen_events["date"] = allergen_events["date_time"].dt.floor("D")

    # Aggregate to daily level (1 if any exposure followed by symptom)
    daily_exposure = (
        allergen_events
        .groupby("date")["symptom"]
        .any()
        .astype(int)
    )

    # --------------------------------------------------
    # Determine if exposure occurred within lag window BEFORE symptom
    # --------------------------------------------------
    symptom_events["allergen_prior"] = symptom_events["date_time"].apply(
        lambda t: exposure_window_prior(allergen_events, t, lag_start, lag_end)
    )

    # Extract date only
    symptom_events["date"] = symptom_events["date_time"].dt.floor("D")

    # Aggregate to daily level (1 if any symptom had prior exposure)
    daily_symptoms = (
        symptom_events
        .groupby("date")["allergen_prior"]
        .any()
        .astype(int)
    )

    # --------------------------------------------------
    # Daily indicator: any symptom occurred on that day
    # --------------------------------------------------
    daily_any_symptom = (
        symptom_events
        .groupby("date")
        .size()
        .gt(0)
        .astype(int)
    )

    # --------------------------------------------------
    # Daily indicator: any exposure occurred on that day
    # --------------------------------------------------
    daily_exposed = (
        allergen_events
        .groupby("date")
        .size()
        .gt(0)
        .astype(int)
    )

    # --------------------------------------------------
    # Create continuous daily date range
    # --------------------------------------------------
    overall_min = min(
        allergen_events["date_time"].min(),
        symptom_events["date_time"].min(),
    )

    overall_max = max(
        allergen_events["date_time"].max(),
        symptom_events["date_time"].max(),
    )

    date_index = pd.date_range(
        start=overall_min.floor("D"),
        end=overall_max.floor("D"),
        freq="D",
        tz="UTC",
    )

    # Create base daily dataframe
    days_df = pd.DataFrame({"date": date_index})

    # --------------------------------------------------
    # Map daily symptom occurrence to full date range
    # --------------------------------------------------
    days_df["any_symptom"] = (
        days_df["date"]
        .map(daily_any_symptom)
        .fillna(0)
        .astype(int)
    )

    # --------------------------------------------------
    # Map daily exposure occurrence to full date range
    # --------------------------------------------------
    days_df["exposed"] = (
        days_df["date"]
        .map(daily_exposed)
        .fillna(0)
        .astype(int)
    )

    return days_df, daily_exposure, daily_symptoms

def count_in_windows(anchor_times, symptom_times, lag_start, lag_end):
    """
    Count the number of symptom events occurring within a forward
    time window after each anchor time.

    For each anchor time, this function counts symptom events in:
        [anchor_time + lag_start, anchor_time + lag_end)

    The implementation uses vectorised NumPy searchsorted for efficiency.

    Parameters
    ----------
    anchor_times : pd.Series or pd.DatetimeIndex
        Array of reference timestamps (e.g., exposure times).
    symptom_times : array-like
        Sorted timestamps of symptom events.
    lag_start : int
        Start of lag window in hours.
    lag_end : int
        End of lag window in hours.

    Returns
    -------
    np.ndarray
        Number of symptom events within the defined window
        for each anchor time.
    """

    # Ensure symptom times are datetime
    symptom_times = pd.to_datetime(symptom_times)

    # Convert lag hours into time deltas
    start_delta = pd.to_timedelta(lag_start, unit="h")
    end_delta = pd.to_timedelta(lag_end, unit="h")

    # Compute window boundaries for each anchor time
    left = anchor_times + start_delta
    right = anchor_times + end_delta

    # Find insertion indices (binary search) for window bounds
    idx_left  = np.searchsorted(symptom_times.values, left.values, side="left")
    idx_right = np.searchsorted(symptom_times.values, right.values, side="right")

    # Number of events within window = difference in indices
    return idx_right - idx_left


def count_window(anchor_time, event_times, start_delta, end_delta):
    """
    Count number of events occurring within a time window
    relative to a single anchor time.

    The window is defined as:
        [anchor_time + start_delta, anchor_time + end_delta)

    Parameters
    ----------
    anchor_time : pd.Timestamp
        Reference timestamp.
    event_times : pd.Series or pd.DatetimeIndex
        Event timestamps to evaluate.
    start_delta : pd.Timedelta
        Start offset relative to anchor_time.
    end_delta : pd.Timedelta
        End offset relative to anchor_time.

    Returns
    -------
    int
        Number of events occurring within the specified window.
    """

    # If there are no events, return 0 immediately
    if event_times.empty:
        return 0

    # Compute window boundaries
    start = anchor_time + start_delta
    end = anchor_time + end_delta

    # Count events within [start, end)
    return (
        (event_times >= start) &
        (event_times < end)
    ).sum()


def temporal_stats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        allergen_name: str=None,
        symptom_group: str=None
    ):

    """
    Compare symptom frequency before vs after allergen exposure
    using a 24-hour window and a one-sided binomial test.

    The function:
    1. Counts symptom events occurring 24h BEFORE exposure.
    2. Counts symptom events occurring 24h AFTER exposure.
    3. Performs a binomial test (H0: equal probability pre vs post).
    4. Returns statistical evidence strength.

    Parameters
    ----------
    current_user : User
        Authenticated user (injected via FastAPI dependency).
    db : Session
        Database session (injected via FastAPI dependency).
    allergen_name : str, optional
        Filter analysis to a specific allergen.
    symptom_group : str, optional
        Filter analysis to a specific symptom group.

    Returns
    -------
    dict
        {
            "post_count": int,
            "pre_count": int,
            "p_value": float or None,
            "evidence": "strong" | "moderate" | "weak" | "not enough data" | "no_data"
        }
    """

    # --------------------------------------------------
    # Load allergen and symptom events
    # --------------------------------------------------
    allergen_events = get_all_allergen_events_df(
        db, current_user.user_id, allergen_name=allergen_name
    )
    symptom_events  = get_all_symptom_events_df(
        db, current_user.user_id, symptom_group=symptom_group
    )

    # Ensure timestamps are timezone-aware
    allergen_events['date_time'] = pd.to_datetime(allergen_events['date_time'], utc=True)
    symptom_events['date_time'] = pd.to_datetime(symptom_events['date_time'], utc=True)

    # --------------------------------------------------
    # Count symptoms in 24h BEFORE exposure
    # --------------------------------------------------
    pre_counts = allergen_events['date_time'].apply(
        lambda a: count_window(
            a,
            symptom_events['date_time'],
            timedelta(hours=-24),
            timedelta(0)
        )
    )
    pre_total = int(pre_counts.sum())

    # --------------------------------------------------
    # Count symptoms in 24h AFTER exposure
    # --------------------------------------------------
    post_counts = allergen_events['date_time'].apply(
        lambda a: count_window(
            a,
            symptom_events['date_time'],
            timedelta(hours=0),
            timedelta(24)
        )
    )
    post_total = int(post_counts.sum())

    # --------------------------------------------------
    # Statistical testing
    # --------------------------------------------------
    # Require minimum number of events for meaningful inference
    if post_total + pre_total < 10:
        return {
            "post_count": post_total,
            "pre_count": pre_total,
            "p_value": None,
            "evidence": "not enough data"
        }

    # Perform one-sided binomial test (post > pre)
    elif post_total + pre_total > 0:
        result = binomtest(
            post_total,
            n=post_total + pre_total,
            p=0.5,
            alternative='greater'
        )
        p_value = result.pvalue

        # Categorise evidence strength
        evidence = (
            "strong" if p_value < 0.01
            else "moderate" if p_value < 0.05
            else "weak"
        )

    else:
        p_value = None
        evidence = "no_data"

    # --------------------------------------------------
    # Return structured results
    # --------------------------------------------------
    return {
        "post_count": post_total,
        "pre_count": pre_total,
        "p_value": float(p_value) if p_value is not None else None,
        "evidence": evidence
    }

def symptom_within_window(symptom_df, exposure_time, lag_start, lag_end):
    """
    Check whether any symptom occurred within a time window
    AFTER a given exposure time.

    Window definition:
        (exposure_time + lag_start, exposure_time + lag_end]

    Returns
    -------
    int
        1 if at least one symptom occurred in window, else 0.
    """

    # Define window boundaries
    window_start = exposure_time + pd.Timedelta(hours=lag_start)
    window_end = exposure_time + pd.Timedelta(hours=lag_end)

    # Boolean mask for symptoms within window
    mask = (
        (symptom_df["date_time"] > window_start) &
        (symptom_df["date_time"] <= window_end)
    )

    return int(mask.any())


def exposure_window_prior(allergen_df, symptom_time, lag_start, lag_end):
    """
    Check whether any allergen exposure occurred within a time window
    BEFORE a given symptom time.

    Window definition:
        (symptom_time - lag_end, symptom_time - lag_start]

    Returns
    -------
    int
        1 if at least one exposure occurred in window, else 0.
    """

    # Define backward-looking window boundaries
    window_start = symptom_time - pd.Timedelta(hours=lag_end)
    window_end = symptom_time - pd.Timedelta(hours=lag_start)

    # Boolean mask for exposures within window
    mask = (
        (allergen_df["date_time"] > window_start) &
        (allergen_df["date_time"] <= window_end)
    )

    return int(mask.any())

