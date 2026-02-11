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
    Compute temporal association statistics between a specific allergen
    and all recorded symptom groups for the current user.

    The endpoint:
    1. Retrieves all allergen exposure events (optionally filtered by allergen).
    2. Retrieves all symptom events for the user.
    3. Iterates over each unique symptom group.
    4. Computes temporal statistics (pre vs post exposure).
    5. Filters out:
        - Symptom groups with fewer than 10 total events.
        - Non-significant results (based on p-value threshold).
    6. Returns results sorted by ascending p-value.

    Parameters
    ----------
    db : Session
        Database session (FastAPI dependency).
    current_user : User
        Authenticated user (FastAPI dependency).
    allergen_name : str, optional
        Name of allergen to analyse. If None, behaviour depends
        on `get_all_allergen_events_df` implementation.

    Returns
    -------
    list[dict]
        A list of dictionaries containing temporal statistics for
        qualifying allergen–symptom group associations.
    """

    # --------------------------------------------------
    # Load allergen exposure and symptom event data
    # --------------------------------------------------
    allergen_events = get_all_allergen_events_df(
        db,
        current_user.user_id,
        allergen_name=allergen_name
    )

    symptom_events = get_all_symptom_events_df(
        db,
        current_user.user_id
    )

    # Extract unique symptom groups
    symptom_groups = symptom_events['symptom_group'].unique()

    results = []

    # --------------------------------------------------
    # Loop through each symptom group and compute stats
    # --------------------------------------------------
    for symptom in symptom_groups:

        # Compute temporal statistics for allergen–symptom pair
        res = temporal_stats(
            current_user=current_user,
            db=db,
            allergen_name=allergen_name,
            symptom_group=symptom
        )

        # Calculate total number of observed events
        total_events = res['pre_count'] + res['post_count']

        # Skip if insufficient data
        if total_events < 10:
            continue

        # --------------------------------------------------
        # Keep only statistically significant results
        # --------------------------------------------------
        if res['p_value'] is not None and res['p_value'] < 1:  # Originally 0.05
            results.append({
                "allergen_name": allergen_name,
                "symptom_group": symptom,
                **res
            })

    # --------------------------------------------------
    # Convert results to DataFrame for sorting/formatting
    # --------------------------------------------------
    results_df = pd.DataFrame(results)

    # Sort by p-value (ascending)
    results_df = results_df.sort_values("p_value").reset_index(drop=True)

    # Return as list of dictionaries (JSON response)
    return results_df.to_dict(orient="records")
