# app/core/jwt.py
from datetime import datetime, timedelta
from jose import jwt
import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")  
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create a signed JWT access token.

    The function:
    1. Copies the provided payload data.
    2. Sets an expiration time (`exp` claim).
    3. Encodes the payload using the configured secret key and algorithm.
    4. Returns the generated JWT string.

    Parameters
    ----------
    data : dict
        Payload data to include in the token (e.g., user identifiers).
    expires_delta : Optional[timedelta]
        Custom expiration time for the token.
        If not provided, defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns
    -------
    str
        Encoded JWT access token.
    """

    # --------------------------------------------------
    # Copy payload data to avoid mutating original input
    # --------------------------------------------------
    to_encode = data.copy()

    # --------------------------------------------------
    # Determine token expiration time
    # --------------------------------------------------
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Add expiration claim to payload
    to_encode.update({"exp": expire})

    # --------------------------------------------------
    # Encode and sign JWT token
    # --------------------------------------------------
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

