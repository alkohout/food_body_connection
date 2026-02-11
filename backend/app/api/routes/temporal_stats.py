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
    current_user: User = Depends(get_current_user),
    allergen_name: str = None
):
    """
    Compute temporal statistics comparing symptom occurrence before vs. after allergen events.

    The endpoint:
    1. Loads allergen events and symptom events for the authenticated user.
    2. Finds all symptom groups present in the user's symptom data.
    3. For each symptom group, calls `temporal_stats` to compute pre/post counts and a p-value.
    4. Filters out results with too few total events (< 10).
    5. Keeps only statistically relevant results (currently `p_value < 1`, placeholder for a stricter threshold).
    6. Returns the results as a list of JSON records sorted by p-value.

    Parameters
    ----------
    db : Session
        Database session (FastAPI dependency).
    current_user : User
        Authenticated user (FastAPI dependency).
    allergen_name : str, optional
        If provided, restricts the analysis to a specific allergen name; if None, uses the default behavior
        of `get_all_allergen_events_df` / `temporal_stats`.

    Returns
    -------
    list[dict]
        A list of result records (one per symptom group) sorted by ascending p-value. Each record contains:
        - allergen_name
        - symptom_group
        - plus keys returned by `temporal_stats` (e.g., pre_count, post_count, p_value, etc.)
    """

    # --------------------------------------------------
    # Load allergen and symptom events for this user
    # --------------------------------------------------
    allergen_events = get_all_allergen_events_df(
        db, current_user.user_id, allergen_name=allergen_name
    )
    symptom_events = get_all_symptom_events_df(db, current_user.user_id)

    # Identify all symptom groups available in the symptom data
    symptom_groups = symptom_events['symptom_group'].unique()

    results = []

    # --------------------------------------------------
    # Loop through symptom groups and compute temporal stats
    # --------------------------------------------------
    for symptom in symptom_groups:
        res = temporal_stats(
            current_user=current_user,
            db=db,
            allergen_name=allergen_name,
            symptom_group=symptom
        )

        # Filter out groups with too few total events for meaningful comparison
        total_events = res['pre_count'] + res['post_count']
        if total_events < 10:
            continue

        # Only keep significant results (currently using p < 1; commonly p < 0.05)
        if res['p_value'] is not None and res['p_value'] < 1:  # 0.05:
            results.append({
                "allergen_name": allergen_name,
                "symptom_group": symptom,
                **res
            })

    # --------------------------------------------------
    # Format results as JSON records
    # --------------------------------------------------
    results_df = pd.DataFrame(results)

    # Sort by p-value (ascending) for easier interpretation
    results_df = results_df.sort_values("p_value").reset_index(drop=True)

    return results_df.to_dict(orient="records")