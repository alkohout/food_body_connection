from fastapi import APIRouter, Query
from fastapi import APIRouter, Depends, Query
from app.models.table_class import User
from app.analysis.temporal_stats import temporal_stats
from app.analysis.temporal_stats_rate import temporal_stats_rate
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.database import get_db
from app.api.routes.auth import get_current_user
import pandas as pd

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/temporal_stats_rate")
def get_temporal_stats_rate(
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
    allergen_name: str=None
):

    # Load all allergen and symptom names for this user
    allergen_events = get_all_allergen_events_df(db, current_user.user_id, allergen_name=allergen_name)
    symptom_events  = get_all_symptom_events_df(db, current_user.user_id)

    symptom_groups  = symptom_events['symptom_group'].unique()

    results = []

    # Loop through all pairs
    for symptom in symptom_groups:
        res = temporal_stats_rate(
            allergen_events = allergen_events,
            symptom_events = symptom_events[symptom_events["symptom_group"] == symptom]
        )

        results.append({
                "allergen_name": allergen_name,
                **res
        })

    # Convert to DataFrame for nice table formatting (optional)
    results_df = pd.DataFrame(results)

    # Optionally sort by p-value ascending
    results_df = results_df.sort_values("p_value").reset_index(drop=True)

    return results_df.to_dict(orient="records")

