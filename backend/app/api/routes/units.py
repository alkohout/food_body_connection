# backend/app/api/routes/unit.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Unit
from app.schemas import UnitOut

router = APIRouter(
    prefix="/units",
    tags=["units"]
)

@router.get("/", response_model=list[UnitOut])
def read_units(db: Session = Depends(get_db)):
    return db.query(Unit).all()

