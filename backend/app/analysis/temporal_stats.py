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
from io import BytesIO

def plot_stats(
    db: Session,
    current_user: User,
    allergen_name: str
    ):

    symptom_events = get_all_symptom_events_df(
        db, current_user.user_id
    )

    n = symptom_events['symptom_group'].nunique()
    fig, axes = plt.subplots(n,1,figsize=(12, 10*n))
    groups = symptom_events['symptom_group'].unique()

    for ax,sg in axes,groups:
        data = days_df(db, current_user,allergen_name = allergen_name, symptom_group = sg) 
        summary = (
            days_df
            .groupby(["exposed", "symptom_0_24h"])
            .size()
            .reset_index(name="count")
        )

        ax.bar(
            summary['count']
        )

        for i, v in enumerate(data["symptom_0_24h"]):
            ax.text(i, v + 0.02, f"{v:.1%}", ha="center")

        plt.tight_layout()

    # --------------------------------------------------
    # Output buffer
    # --------------------------------------------------
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
):

    allergen_events = get_all_allergen_events_df(
        db, current_user.user_id, allergen_name=allergen_name
    )
    symptom_events = get_all_symptom_events_df(
        db, current_user.user_id, symptom_group=symptom_group
    )

    allergen_events["date_time"] = pd.to_datetime(allergen_events["date_time"], utc=True)
    symptom_events["date_time"] = (
        pd.to_datetime(symptom_events["date_time"], utc=True)
        .sort_values()
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

    days_df = pd.DataFrame({"date": date_index})

    # Exposure days
    allergen_events["date"] = allergen_events["date_time"].dt.floor("D")
    exposed_days = (
        allergen_events[["date"]]
        .drop_duplicates()
        .assign(exposed=1)
    )

    days_df = days_df.merge(exposed_days, on="date", how="left")
    days_df["exposed"] = days_df["exposed"].fillna(0).astype(int)

    # Vectorised symptom-in-24h check
    anchors = allergen_events["date_time"]
    symptom_times = symptom_events["date_time"]

    has_symptom = count_in_windows(
        anchors,
        symptom_times,
        timedelta(hours=0),
        timedelta(hours=24),
    ) > 0

    exposure_windows = allergen_events.assign(symptom_0_24h=has_symptom.astype(int))

    daily_symptoms = (
        exposure_windows
        .groupby("date")["symptom_0_24h"]
        .max()
        .reset_index()
    )

    days_df = days_df.merge(daily_symptoms, on="date", how="left")
    days_df["symptom_0_24h"] = days_df["symptom_0_24h"].fillna(0).astype(int)

    return days_df


def count_in_windows(anchor_times, symptom_times, start_delta, end_delta):
    """
    Count symptom events within [anchor + start_delta, anchor + end_delta)
    for each anchor time.
    """
    symptom_times = np.asarray(symptom_times.values)
    left = anchor_times.values + start_delta
    right = anchor_times.values + end_delta

    idx_left = np.searchsorted(symptom_times, left, side="left")
    idx_right = np.searchsorted(symptom_times, right, side="right")

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