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
    current_user: int,
    allergen_name: str
    ):

    symptom_events = get_all_symptom_events_df(
        db, current_user
    )

    n = symptom_events['symptom_group'].nunique()
    fig, axes = plt.subplots(n,1,figsize=(12, 10))
    groups = symptom_events['symptom_group'].unique()

    for ax,sg in zip(axes,groups):

        data = days_df(db, current_user, allergen_name = allergen_name, symptom_group = sg) 

        summary = (
            data
            .groupby(["allergen_prior_symptom", "symptom_following_exposure"])
            .size()
            .reset_index(name="count")
        )

        # Ensure all four combinations exist
        all_combos = pd.DataFrame([
            {"allergen_prior_symptom": 0, "symptom_following_exposure": 0},
            {"allergen_prior_symptom": 0, "symptom_following_exposure": 1},
            {"allergen_prior_symptom": 1, "symptom_following_exposure": 0},
            {"allergen_prior_symptom": 1, "symptom_following_exposure": 1},
        ])

        summary = all_combos.merge(summary, on=["allergen_prior_symptom", "symptom_following_exposure"], how="left")
        summary["count"] = summary["count"].fillna(0)

        # Drop No exposure & No symptoms
        summary = summary[~(
            (summary["allergen_prior_symptom"] == 0) &
            (summary["symptom_following_exposure"] == 0)
        )]

        labels = (
            summary["allergen_prior_symptom"].map({0: "NoExp", 1: "Exp"})
            + "_"
            + summary["symptom_following_exposure"].map({0: "NoSym", 1: "Sym"})
        )

        heights = summary["count"].values

        ax.bar(labels, heights)
        ax.set_title(sg)
        ax.set_ylabel("Days Count")
        ax.set_ylim(0, heights.max() * 1.1)  # add 10% headroom


        plt.xticks(rotation=45)
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
        db, current_user, allergen_name=allergen_name
    )
    symptom_events = get_all_symptom_events_df(
        db, current_user, symptom_group=symptom_group
    )

    allergen_events["date_time"] = pd.to_datetime(allergen_events["date_time"], utc=True)
    allergen_events = allergen_events.sort_values("date_time")
    symptom_events["date_time"] = pd.to_datetime(symptom_events["date_time"], utc=True)
    symptom_events = symptom_events.sort_values("date_time")

    symptom_times = symptom_events["date_time"].values
    allergen_events["symptom_0_24h"] = allergen_events["date_time"].apply(
        lambda t: symptom_within_24h(symptom_times, t)
    )
    allergen_events["date"] = allergen_events["date_time"].dt.floor("D")

    daily_exposure = (
        allergen_events
        .groupby("date")["symptom_0_24h"]
        .any()
        .astype(int)
    )

    allergen_times = allergen_events["date_time"].values
    symptom_events["allergen_0_24h_prior"] = symptom_events["date_time"].apply(
        lambda t: exposure_24h_prior(allergen_times,t)
    )
    symptom_events["date"] = symptom_events["date_time"].dt.floor("D")
    daily_symptoms = (
        symptom_events
        .groupby("date")["allergen_0_24h_prior"]
        .any()
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


    days_df = pd.DataFrame({"date": date_index})
    n = len(days_df)

    days_df["allergen_prior_symptom"] = (
        days_df["date"]
        .map(daily_symptoms)
        .fillna(0)
        .astype(int)
    )

    days_df["symptom_following_exposure"] = (
        days_df["date"]
        .map(daily_exposure)
        .fillna(0)
        .astype(int)
    )

    return days_df


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

def symptom_within_24h(symptom_times,exposure_time):
    idx = np.searchsorted(symptom_times, exposure_time, side="right")
    if idx == len(symptom_times):
        return False
    return symptom_times[idx] <= exposure_time + timedelta(hours=24)



def exposure_24h_prior(allergen_times,symptom_time):
    # Find the index of the first allergen AFTER the symptom
    idx = np.searchsorted(allergen_times, symptom_time, side="right")  # first exposure > symptom
    if idx == 0:
        # No prior exposures
        return 0
    # The most recent exposure before symptom
    last_exposure = allergen_times[idx - 1]
    return int(symptom_time - last_exposure <= timedelta(hours=24))



