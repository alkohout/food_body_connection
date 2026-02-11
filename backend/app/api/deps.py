# app/api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.models.table_class import User
from app.core.jwt import SECRET_KEY, ALGORITHM
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    Validate the JWT access token and return the authenticated user.

    The function:
    1. Extracts the JWT token from the OAuth2 dependency.
    2. Decodes the token using the configured secret key and algorithm.
    3. Extracts `sub` (user_id) and `email` from the payload.
    4. Verifies required fields are present.
    5. Fetches the corresponding user from the database.
    6. Raises HTTP 401 if validation fails at any step.

    Parameters
    ----------
    token : str
        JWT access token provided via OAuth2 dependency.
    db : Session
        Database session (FastAPI dependency).

    Returns
    -------
    User
        Authenticated user object from the database.

    Raises
    ------
    HTTPException (401)
        If the token is invalid, expired, malformed,
        or the user does not exist.
    """

    try:
        # --------------------------------------------------
        # Decode JWT token
        # --------------------------------------------------
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Extract user identifiers from payload
        user_id: str = payload.get("sub")
        email: str = payload.get("email")

        # Validate required token fields
        if user_id is None:
            raise HTTPException(status_code=401)

        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")

    except JWTError:
        # Token decoding failed (invalid/expired/malformed)
        raise HTTPException(status_code=401, detail="Invalid token")

    # --------------------------------------------------
    # Fetch user from database
    # --------------------------------------------------
    user = db.query(User).filter(User.email == email).first()

    # If user does not exist, reject request
    if not user:
        raise HTTPException(status_code=401)

    # Return authenticated user object
    return user

