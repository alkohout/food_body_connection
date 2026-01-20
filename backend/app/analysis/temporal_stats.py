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

    fig, ax = plt.subplots(figsize=(12, 10))

    days, exposures, symptoms = days_df(db, current_user, allergen_name = allergen_name, symptom_group = symptom_group, lag_start=lag_start, lag_end=lag_end) 

    e_perc = 100*exposures.sum()/len(exposures)
    s_perc = 100*symptoms.sum()/len(symptoms)

    labels = [f'Exposure-days followed by symptoms (within {lag_start} - {lag_end} hrs)', f'Symptom-days preceded by exposure (within {lag_start} - {lag_end} hrs)']
    heights = [e_perc,s_perc] 

    ax.bar(labels, heights)
    ax.set_title(symptom_group)
    ax.set_ylabel("Percent")
    ax.set_ylim(0, max(heights) * 1.1)  # add 10% headroom
    plt.tight_layout()

    # --------------------------------------------------
    # Output buffer
    # --------------------------------------------------
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

def get_pvalue_colour(p):
    """
    Return traffic light color based on p-value.
    Green = highly significant
    Orange = borderline
    Red = not significant
    """
    if p < 0.01:
        return "green"
    elif p < 0.05:
        return "orange"
    else:
        return "red"

def get_risk_colour(r):
    if r > 10:
        return "green"
    elif r > 3:
        return "orange"
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
    fig, ax = plt.subplots(figsize=(12, 10))

    # Get daily data
    days, exposures, symptoms = days_df(
        db,
        current_user,
        allergen_name=allergen_name,
        symptom_group=symptom_group,
        lag_start=lag_start,
        lag_end=lag_end
    )

    # Split into exposed vs unexposed days
    exposed_days = days[days["exposed"] == 1]
    unexposed_days = days[days["exposed"] == 0]

    # Calculate absolute risks
    risk_exposed = exposed_days["any_symptom"].mean()
    risk_unexposed = unexposed_days["any_symptom"].mean()
    risks = [100 * risk_unexposed, 100 * risk_exposed]
    labels = ["No exposure (baseline)", f"Exposure to {allergen_name}"]

    # Plot bars
    ax.bar(labels, risks)
    ax.set_ylabel("Percent of days with symptoms")
    ax.set_ylim(0, max(risks) * 1.25)

    # Annotate absolute risk difference
    risk_diff = 100 * (risk_exposed - risk_unexposed)

    # Fisher's exact test
    table = [
        [exposed_days["any_symptom"].sum(), exposed_days.shape[0] - exposed_days["any_symptom"].sum()],
        [unexposed_days["any_symptom"].sum(), unexposed_days.shape[0] - unexposed_days["any_symptom"].sum()]
    ]
    _, p_value = fisher_exact(table)

    # Traffic light annotation for p-value
    p_color = get_pvalue_colour(p_value)
    r_color = get_risk_colour(risk_diff)
    x_text = 0.95
    y_start = 0.95
    y = y_start 
    text = f"p-value: {p_value:.3f}" 
    plt.text(x_text, y, text, transform=ax.transAxes, fontsize=12,
                    verticalalignment="top", horizontalalignment="right",
                    color=p_color, zorder=4)
    ax.text(
        x_text,
        y - .05,
        f"Absolute risk difference: {risk_diff:+.1f}%",
        transform=ax.transAxes, 
        fontsize=12,
        verticalalignment="top", 
        horizontalalignment="right",
        color=r_color, zorder=3
    )

    from matplotlib.patches import Rectangle
    rect = Rectangle((0.7, 0.8), 0.3, 0.2, transform=ax.transAxes, color="white", alpha=0.85, zorder=2)
    ax.add_patch(rect)

    # Set title
    ax.set_title(
        f"{symptom_group}\nSymptoms within {lag_start}–{lag_end} hours",
        fontsize=16
    )

    plt.tight_layout()

    # Save to buffer
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
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

    allergen_events = get_all_allergen_events_df(
        db, current_user, allergen_name=allergen_name
    )
    symptom_events = get_all_symptom_events_df(
        db, current_user, symptom_group=symptom_group
    )

    allergen_events["date_time"] = pd.to_datetime(allergen_events["date_time"], utc=True)
    allergen_events = allergen_events.sort_values("date_time")
    symptom_events["date_time"] = pd.to_datetime(symptom_events["date_time"], utc=True)
    symptom_events = symptom_events.sort_values("date_time")

    allergen_events["symptom"] = allergen_events["date_time"].apply(
        lambda t: symptom_within_window(symptom_events, t, lag_start, lag_end)
    )
    allergen_events["date"] = allergen_events["date_time"].dt.floor("D")

    daily_exposure = (
        allergen_events
        .groupby("date")["symptom"]
        .any()
        .astype(int)
    )

    symptom_events["allergen_prior"] = symptom_events["date_time"].apply(
        lambda t: exposure_window_prior(allergen_events,t,lag_start,lag_end)
    )
    symptom_events["date"] = symptom_events["date_time"].dt.floor("D")
    daily_symptoms = (
        symptom_events
        .groupby("date")["allergen_prior"]
        .any()
        .astype(int)
    )

    daily_any_symptom = (
        symptom_events
        .groupby("date")
        .size()
        .gt(0)
        .astype(int)
    )


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

    daily_exposed = (
        allergen_events
        .groupby("date")
        .size()
        .gt(0)
        .astype(int)
    )

    days_df = pd.DataFrame({"date": date_index})

    days_df["any_symptom"] = (
        days_df["date"]
        .map(daily_any_symptom)
        .fillna(0)
        .astype(int)
    )

    days_df["exposed"] = (
        days_df["date"]
        .map(daily_exposed)
        .fillna(0)
        .astype(int)
    )


    return days_df, daily_exposure, daily_symptoms


def count_in_windows(anchor_times, symptom_times, lag_start, lag_end):
    """
    Count symptom events within [anchor + start_delta, anchor + end_delta)
    for each anchor time.
    """
    symptom_times = pd.to_datetime(symptom_times)

    start_delta = pd.to_timedelta(lag_start, unit="h")
    end_delta = pd.to_timedelta(lag_end, unit="h")
    left = anchor_times + start_delta
    right = anchor_times + end_delta

    idx_left  = np.searchsorted(symptom_times.values, left.values, side="left")
    idx_right = np.searchsorted(symptom_times.values, right.values, side="right")

    return idx_right - idx_left

def count_window(anchor_time, event_times, start_delta, end_delta):
    if event_times.empty:
        return 0

    start = anchor_time + start_delta
    end = anchor_time + end_delta

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

    allergen_events = get_all_allergen_events_df(db, current_user.user_id, allergen_name=allergen_name)
    symptom_events  = get_all_symptom_events_df(db, current_user.user_id, symptom_group=symptom_group)

    allergen_events['date_time'] = pd.to_datetime(allergen_events['date_time'], utc=True)
    symptom_events['date_time'] = pd.to_datetime(symptom_events['date_time'], utc=True)

    pre_counts = allergen_events['date_time'].apply(
        lambda a: count_window(
            a,
            symptom_events['date_time'],
            timedelta(hours=-24),
            timedelta(0)
        )
    )
    pre_total = int(pre_counts.sum())
    post_counts = allergen_events['date_time'].apply(
        lambda a: count_window(
            a,
            symptom_events['date_time'],
            timedelta(hours=0),
            timedelta(24)
        )
    )
    post_total = int(post_counts.sum())

    if post_total + pre_total < 10:
        return {
            "post_count": post_total,
            "pre_count": pre_total,
            "p_value": None,
            "evidence": "not enough data"
        }
    elif post_total + pre_total > 0:
        result = binomtest(post_total, n=post_total + pre_total, p=0.5, alternative='greater')
        p_value = result.pvalue
        evidence = "strong" if p_value < 0.01 else "moderate" if p_value < 0.05 else "weak"
    else:
        p_value = None
        evidence = "no_data"

    return {
        "post_count": post_total,
        "pre_count": pre_total,
        "p_value": float(p_value) if p_value is not None else None,
        "evidence": evidence
    }

def symptom_within_window(symptom_df, exposure_time, lag_start, lag_end):
    # Check if any symptom occurs within window after exposure_time
    window_start = exposure_time + pd.Timedelta(hours=lag_start)
    window_end = exposure_time + pd.Timedelta(hours=lag_end)
    mask = (symptom_df["date_time"] > window_start) & (symptom_df["date_time"] <= window_end)
    return int(mask.any())

def exposure_window_prior(allergen_df, symptom_time, lag_start, lag_end):
    # Check if any allergen occurred within window before symptom_time
    window_start = symptom_time - pd.Timedelta(hours=lag_end)
    window_end = symptom_time - pd.Timedelta(hours=lag_start)
    mask = (allergen_df["date_time"] > window_start) & (allergen_df["date_time"] <= window_end)
    return int(mask.any())


