# backend/app/api/routes/symptoms.py

from fastapi import APIRouter, Depends, Query
from app.api.routes.auth import get_current_user
from app.models.table_class import User
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Symptom

router = APIRouter(prefix="/symptoms", tags=["symptoms"], include_in_schema=True)

@router.get("")
def search_symptoms(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    query = (
        db.query(Symptom)
        .filter(Symptom.user_id == current_user.user_id)
    )

    results = (
        query.filter(Symptom.symptom_name.ilike(f"%{q}%"))
             .order_by(Symptom.symptom_name)
             .limit(10)
             .all()
    )

    return [
        {
            "symptom_id": a.symptom_id,
            "symptom_name": a.symptom_name
        }
        for a in results
    ]


