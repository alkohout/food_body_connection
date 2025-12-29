from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Allergen

router = APIRouter(prefix="/allergens", tags=["allergens"], include_in_schema=True)

@router.get("")
def search_allergens(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    results = (
        db.query(Allergen)
        .filter(Allergen.allergen_name.ilike(f"%{q}%"))
        .order_by(Allergen.allergen_name)
        .limit(10)
        .all()
    )

    return [
        {
            "allergen_id": a.allergen_id,
            "allergen_name": a.allergen_name
        }
        for a in results
    ]

