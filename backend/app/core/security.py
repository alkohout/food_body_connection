# app/core/security.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Hash a plaintext password using the configured password context.

    The function:
    1. Encodes the password as UTF-8 bytes.
    2. Truncates to 72 bytes (bcrypt maximum input length).
    3. Returns a securely hashed version of the password.

    Parameters
    ----------
    password : str
        Plaintext password provided by the user.

    Returns
    -------
    str
        Securely hashed password string.
    """

    # --------------------------------------------------
    # Truncate password to 72 bytes (bcrypt limit)
    # --------------------------------------------------
    password_bytes = password.encode('utf-8')[:72]

    # Hash password using configured password context
    return pwd_context.hash(password_bytes)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored hash.

    The function:
    1. Compares the provided plaintext password with the stored hash.
    2. Returns True if they match, otherwise False.

    Parameters
    ----------
    plain_password : str
        Plaintext password provided during login.
    hashed_password : str
        Previously stored hashed password.

    Returns
    -------
    bool
        True if password is valid, False otherwise.
    """

    # --------------------------------------------------
    # Verify password using configured password context
    # --------------------------------------------------
    return pwd_context.verify(plain_password, hashed_password)
