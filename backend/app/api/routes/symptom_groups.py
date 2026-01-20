# backend/app/api/routes/symptom_groups.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Symptom

router = APIRouter(prefix="/symptom_groups", tags=["symptom_groups"], include_in_schema=True)

@router.get("")
def search_symptom_groups(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):

    results = (
        db.query(Symptom.symptom_group)
        .filter(Symptom.symptom_group.ilike(f"%{q}%"))
        .distinct()  # <- only unique values
        .order_by(Symptom.symptom_group)
        .limit(10)
        .all()
    )

    return [{"symptom_group": sg[0]} for sg in results]  



