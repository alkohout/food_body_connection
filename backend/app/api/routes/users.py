# app/api/routes/users.py
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.models.table_class import User

router = APIRouter()

@router.get("/me")
def read_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.user_id, "email": current_user.email}

