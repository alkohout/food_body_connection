import os
import json
import logging

import anthropic
import pandas as pd
from scipy.stats import binomtest

from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.analysis.model import model_classification
from app.models.table_class import UserDocument

logger = logging.getLogger(__name__)


def _time_of_day(h: int) -> str:
    if 5 <= h < 12:
        return "morning"
    elif 12 <= h < 17:
        return "afternoon"
    elif 17 <= h < 21:
        return "evening"
    else:
        return "night"


def build_analysis_context(db, user_id: int) -> dict | None:
    allergen_df = get_all_allergen_events_df(db, user_id)
    symptom_df = get_all_symptom_events_df(db, user_id)

    if allergen_df.empty or symptom_df.empty:
        return None

    allergen_df["date_time"] = pd.to_datetime(allergen_df["date_time"], utc=True)
    symptom_df["date_time"] = pd.to_datetime(symptom_df["date_time"], utc=True)

    all_times = pd.concat([allergen_df["date_time"], symptom_df["date_time"]])
    start_date = all_times.min().strftime("%Y-%m-%d")
    end_date = all_times.max().strftime("%Y-%m-%d")
    total_days = (all_times.max() - all_times.min()).days + 1

    allergen_counts = allergen_df.groupby("allergen_name").size().sort_values(ascending=False)

    has_groups = "symptom_group" in symptom_df.columns
    symptom_group_counts = (
        symptom_df.groupby("symptom_group").size().sort_values(ascending=False).to_dict()
        if has_groups else {}
    )

    symptom_group_intensity = {}
    if has_groups and "symptom_intensity" in symptom_df.columns:
        symptom_group_intensity = (
            symptom_df.dropna(subset=["symptom_intensity"])
            .groupby("symptom_group")["symptom_intensity"]
            .mean()
            .round(2)
            .to_dict()
        )

    symptom_df["hour"] = symptom_df["date_time"].dt.hour
    symptom_df["time_of_day"] = symptom_df["hour"].map(_time_of_day)
    peak_time = symptom_df["time_of_day"].value_counts().idxmax()

    symptom_df["day_of_week"] = symptom_df["date_time"].dt.day_name()
    busiest_days = (
        symptom_df.groupby("day_of_week").size()
        .sort_values(ascending=False)
        .head(3)
        .to_dict()
    )

    top_allergens_list = allergen_counts.head(5).index.tolist()
    top_groups_list = list(symptom_group_counts.keys())[:3]
    cross_stats = []

    for allergen_name in top_allergens_list:
        a_times = allergen_df[allergen_df["allergen_name"] == allergen_name]["date_time"]
        for group in top_groups_list:
            s_times = (
                symptom_df[symptom_df["symptom_group"] == group]["date_time"]
                if has_groups
                else pd.Series(dtype="datetime64[ns, UTC]")
            )
            if s_times.empty or a_times.empty:
                continue

            post_count = 0
            pre_count = 0
            for t in a_times:
                post_count += int(
                    ((s_times >= t) & (s_times < t + pd.Timedelta(hours=24))).sum()
                )
                pre_count += int(
                    ((s_times >= t - pd.Timedelta(hours=24)) & (s_times < t)).sum()
                )

            if post_count + pre_count >= 10:
                result = binomtest(
                    int(post_count),
                    n=int(post_count + pre_count),
                    p=0.5,
                    alternative="greater",
                )
                p_val = round(result.pvalue, 4)
                evidence = "strong" if p_val < 0.01 else "moderate" if p_val < 0.05 else "weak"
            else:
                p_val = None
                evidence = "insufficient data"

            cross_stats.append({
                "allergen": allergen_name,
                "symptom_group": group,
                "symptoms_within_24h_after_exposure": int(post_count),
                "symptoms_within_24h_before_exposure": int(pre_count),
                "p_value": p_val,
                "temporal_evidence": evidence,
            })

    try:
        model_text = model_classification(db, user_id, return_type="text")
    except Exception as exc:
        logger.warning("model_classification failed: %s", exc)
        model_text = "Logistic regression model could not be run (likely insufficient data)."

    return {
        "date_range": f"{start_date} to {end_date}",
        "total_tracking_days": int(total_days),
        "total_allergen_logs": int(len(allergen_df)),
        "total_symptom_logs": int(len(symptom_df)),
        "unique_allergens_tracked": int(allergen_df["allergen_name"].nunique()),
        "unique_symptom_groups": (
            int(symptom_df["symptom_group"].nunique()) if has_groups else 0
        ),
        "allergen_frequency": allergen_counts.head(15).to_dict(),
        "symptom_group_frequency": symptom_group_counts,
        "symptom_group_avg_intensity_1_to_10": symptom_group_intensity,
        "symptom_peak_time_of_day": peak_time,
        "busiest_symptom_days_of_week": busiest_days,
        "allergen_to_symptom_temporal_analysis": cross_stats,
        "logistic_regression_summary": model_text,
    }


_DOC_CHAR_LIMIT = 8000
_DOC_TOTAL_CHAR_LIMIT = 24000  # across all documents combined


def _get_document_context(db, user_id: int) -> str:
    docs = (
        db.query(UserDocument)
        .filter(
            UserDocument.user_id == user_id,
            UserDocument.extracted_text.isnot(None),
        )
        .order_by(UserDocument.uploaded_at.desc())
        .all()
    )
    if not docs:
        return ""

    parts = []
    total_chars = 0
    for doc in docs:
        if total_chars >= _DOC_TOTAL_CHAR_LIMIT:
            parts.append(f"### [further documents omitted — combined limit reached]")
            break
        text = doc.extracted_text or ""
        remaining = _DOC_TOTAL_CHAR_LIMIT - total_chars
        per_doc_limit = min(_DOC_CHAR_LIMIT, remaining)
        truncated = len(text) > per_doc_limit
        snippet = text[:per_doc_limit] + (" [truncated]" if truncated else "")
        total_chars += len(snippet)
        label = doc.description or doc.filename
        parts.append(f"### {label}\n{snippet}")

    return "\n\n".join(parts)


def generate_ai_summary(db, user_id: int) -> dict:
    context = build_analysis_context(db, user_id)

    if context is None:
        return {
            "text": (
                "Not enough data to generate a summary yet. "
                "Please log more allergen and symptom events to see patterns."
            ),
            "input_tokens": None,
            "output_tokens": None,
        }

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — falling back to model text")
        try:
            text = model_classification(db, user_id, return_type="text")
        except Exception:
            text = "Summary unavailable: ANTHROPIC_API_KEY is not configured."
        return {"text": text, "input_tokens": None, "output_tokens": None}

    doc_context = _get_document_context(db, user_id)
    doc_section = (
        f"\n\n--- USER HEALTH DOCUMENTS ---\n{doc_context}\n"
        if doc_context
        else ""
    )

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a health data analyst helping a user understand patterns in their personal food and symptom tracking data. Based on the structured analysis below, write a clear, empathetic, and insightful summary (3–4 paragraphs) that:

1. Highlights the most important food–symptom associations found
2. Explains the statistical evidence in plain English (e.g. "strong evidence" not "p < 0.01")
3. Notes any interesting temporal or behavioural patterns (time of day, day of week, most logged items)
4. Gives 1–2 practical, specific observations the user might act on
5. If health documents are provided below, reference any relevant context from them (e.g. diagnosed conditions, test results, medications) to personalise the analysis — but do not repeat their full content

Write in second person ("Your data shows..."). Use specific numbers where helpful. Where evidence is weak or data is limited, say so honestly. Do not make medical diagnoses or treatment recommendations.

--- TRACKING DATA ---
{json.dumps(context, indent=2, default=str)}{doc_section}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "text": message.content[0].text,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }
