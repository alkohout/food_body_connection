# backend/app/api/routes/unit.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Unit
from app.schemas.entry import UnitOut

router = APIRouter(
    prefix="/units",
    tags=["units"]
)

@router.get("", response_model=list[UnitOut])
def read_units(db: Session = Depends(get_db)):
    """
    Retrieve all measurement units.

    The endpoint:
    1. Queries the `Unit` table.
    2. Returns all stored unit records.
    3. Serializes results using the `UnitOut` response model.

    Parameters
    ----------
    db : Session
        Database session (FastAPI dependency).

    Returns
    -------
    list[UnitOut]
        A list of unit objects formatted according to the
        `UnitOut` response schema.
    """

    # --------------------------------------------------
    # Query all units from the database
    # --------------------------------------------------
    return db.query(Unit).all()

