# app/api/routes/users.py
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.models.table_class import User

router = APIRouter()


@router.get("/me")
def read_me(current_user: User = Depends(get_current_user)):
    """
    Retrieve details for the currently authenticated user.

    The endpoint:
    1. Uses the `get_current_user` dependency to authenticate the request.
    2. Returns basic user information (ID and email).

    Parameters
    ----------
    current_user : User
        Authenticated user (FastAPI dependency).

    Returns
    -------
    dict
        Dictionary containing:
        {
            "id": int,
            "email": str
        }
    """

    # --------------------------------------------------
    # Return authenticated user's basic information
    # --------------------------------------------------
    return {
        "id": current_user.user_id,
        "email": current_user.email
    }

