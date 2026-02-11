from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.table_class import Allergen
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/allergens", tags=["allergens"])

class AllergenCreate(BaseModel):
    allergen_name: str

@router.post("")
def create_allergen(
    payload: AllergenCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Create a new allergen for the current user.

    The endpoint:
    1. Strips whitespace from the allergen name.
    2. Checks if the allergen already exists (case-insensitive).
    3. Creates and saves a new allergen if not duplicate.
    4. Returns confirmation with allergen details.

    Parameters
    ----------
    payload : AllergenCreate
        Request body containing the allergen name.
    db : Session
        Database session (FastAPI dependency).
    current_user : User
        Authenticated user (FastAPI dependency).

    Returns
    -------
    dict
        {
            "message": str,
            "allergen_id": int,
            "allergen_name": str
        }
    """

    # --------------------------------------------------
    # Clean input (remove leading/trailing whitespace)
    # --------------------------------------------------
    name = payload.allergen_name.strip()

    # --------------------------------------------------
    # Check if allergen already exists for this user
    # (case-insensitive comparison)
    # --------------------------------------------------
    existing = (
        db.query(Allergen)
        .filter(Allergen.user_id == current_user.user_id)
        .filter(Allergen.allergen_name.ilike(name))
        .first()
    )

    if existing:
        raise HTTPException(400, "Allergen already exists for this user")

    # --------------------------------------------------
    # Create new allergen record
    # --------------------------------------------------
    new_allergen = Allergen(
        user_id=current_user.user_id,
        allergen_name=name
    )

    db.add(new_allergen)
    db.commit()
    db.refresh(new_allergen)

    # --------------------------------------------------
    # Return response
    # --------------------------------------------------
    return {
        "message": "Allergen created",
        "allergen_id": new_allergen.allergen_id,
        "allergen_name": new_allergen.allergen_name
    }