from fastapi import APIRouter, Query
from fastapi import APIRouter, Depends, Query
from app.models.table_class import User
from app.analysis.temporal_stats import temporal_stats
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.database import get_db
from app.api.routes.auth import get_current_user
import pandas as pd

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/temporal_stats")
def get_temporal_stats(
    db = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    # Load all allergen and symptom names for this user
    allergen_events = get_all_allergen_events_df(db, current_user.user_id)
    symptom_events  = get_all_symptom_events_df(db, current_user.user_id)

    allergen_names = allergen_events['allergen_name'].unique()
    symptom_names  = symptom_events['symptom_name'].unique()

    results = []

    # Loop through all pairs
    for allergen in allergen_names:
        for symptom in symptom_names:
            res = temporal_stats(
                current_user=current_user,
                db=db,
                allergen_name=allergen,
                symptom_name=symptom
            )

            # Only keep significant results (p < 0.05)
            if res['p_value'] is not None and res['p_value'] < 1:#0.05:
                results.append({
                    "allergen_name": allergen,
                    "symptom_name": symptom,
                    **res
                })

    # Convert to DataFrame for nice table formatting (optional)
    results_df = pd.DataFrame(results)

    # Optionally sort by p-value ascending
    results_df = results_df.sort_values("p_value").reset_index(drop=True)

    return results_df.to_dict(orient="records")

