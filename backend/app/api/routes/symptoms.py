# backend/app/api/routes/symptoms.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Symptom 

router = APIRouter(prefix="/symptoms", tags=["symptoms"], include_in_schema=True)

@router.get("")
def search_symptoms(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    results = (
        db.query(Symptom)
        .filter(Symptom.symptom_name.ilike(f"%{q}%"))
        .order_by(Symptom.symptom_name)
        .limit(10)
        .all()
    )

    return [
        {
            "symptom_id": a.symmptom_id,
            "symptom_name": a.symptom_name
        }
        for a in results
    ]


