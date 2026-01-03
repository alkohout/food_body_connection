# backend/app/analysis/temporal_stats.py

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

def count_window(a_time, s_time, start_offset, end_offset):
    start = a_time + start_offset
    end   = a_time + end_offset
    return ((s_time >= start) & (s_time < end)).sum()

def temporal_stats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        allergen_name: str=None,
        symptom_name: str=None
    ):

    allergen_events = get_all_allergen_events_df(db, current_user.user_id, allergen_name=allergen_name)
    symptom_events  = get_all_symptom_events_df(db, current_user.user_id, symptom_name=symptom_name)

    allergen_events['date_time'] = pd.to_datetime(allergen_events['date_time'])
    symptom_events['date_time']  = pd.to_datetime(symptom_events['date_time'])

    pre_total = allergen_events['date_time'].apply(lambda a: count_window(a, symptom_events['date_time'], timedelta(hours=-24), timedelta(0))).sum()
    post_total = allergen_events['date_time'].apply(lambda a: count_window(a, symptom_events['date_time'], timedelta(0), timedelta(hours=24))).sum()

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
        "p_value": round(p_value, 4) if p_value is not None else None,
        "evidence": evidence
    }

