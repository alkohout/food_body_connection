# app/api/routes/auth.py
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import User, Allergen, Symptom, PasswordResetToken
from app.schemas.user import UserCreate, UserOut
from app.core.security import hash_password, verify_password
from app.core.email import send_reset_email
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from app.core.jwt import create_access_token, SECRET_KEY, ALGORITHM
from jose import JWTError, jwt
from datetime import datetime, timezone
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@router.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.

    The endpoint:
    1. Validates that the email is not already registered.
    2. Creates a new user with hashed password.
    3. Clones seed symptoms and allergens from a predefined template user.
    4. Returns the newly created user.

    Parameters
    ----------
    user : UserCreate
        Incoming user registration data (email + password).
    db : Session
        Database session (FastAPI dependency).

    Returns
    -------
    UserOut
        Newly created user object.
    """

    # --------------------------------------------------
    # Check if email is already registered
    # --------------------------------------------------
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # --------------------------------------------------
    # Create the user
    # --------------------------------------------------
    new_user = User(
        email=user.email,
        password_hash=hash_password(user.password),  # Securely hash password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # --------------------------------------------------
    # Clone seed symptoms & allergens to the new user
    # --------------------------------------------------

    # Define the template ("seed") user
    SEED_USER_EMAIL = "seed@data.com"
    seed_user = db.query(User).filter(User.email == SEED_USER_EMAIL).first()

    # Ensure seed data exists
    if not seed_user:
        raise HTTPException(
            status_code=500,
            detail="Seed user not found; run seed_data.py first"
        )

    # Fetch seed symptoms
    seed_symptoms = db.query(Symptom).filter(
        Symptom.user_id == seed_user.user_id
    ).all()

    # Fetch seed allergens
    seed_allergens = db.query(Allergen).filter(
        Allergen.user_id == seed_user.user_id
    ).all()

    # Clone symptoms for new user
    for s in seed_symptoms:
        db.add(Symptom(
            symptom_name=s.symptom_name,
            symptom_group=s.symptom_group,
            user_id=new_user.user_id
        ))

    # Clone allergens for new user
    for a in seed_allergens:
        db.add(Allergen(
            allergen_name=a.allergen_name,
            user_id=new_user.user_id
        ))

    db.commit()

    return new_user

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate a user and return a JWT access token.

    The endpoint:
    1. Validates email and password.
    2. Generates a JWT access token.
    3. Returns token in OAuth2-compatible format.

    Parameters
    ----------
    form_data : OAuth2PasswordRequestForm
        OAuth2 login form (username=email, password).
    db : Session
        Database session.

    Returns
    -------
    dict
        {
            "access_token": str,
            "token_type": "bearer"
        }
    """

    # Fetch user by email (username field)
    user = db.query(User).filter(User.email == form_data.username).first()

    # Validate credentials
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create JWT access token
    access_token = create_access_token(
        data={
            "sub": str(user.user_id),
            "email": user.email
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Validate JWT token and return authenticated user.

    The function:
    1. Decodes JWT.
    2. Extracts user ID from token payload.
    3. Fetches user from database.
    4. Raises 401 if invalid.

    Parameters
    ----------
    token : str
        JWT token from Authorization header.
    db : Session
        Database session.

    Returns
    -------
    User
        Authenticated user object.
    """

    try:
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Retrieve user from database
    user = db.query(User).filter(User.user_id == int(user_id)).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

@router.get("/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Return the currently authenticated user's details.

    This is a protected route that requires a valid JWT.

    Returns
    -------
    UserOut
        Current user's public information.
    """
    return current_user


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()

    # Always return the same response to avoid exposing whether an email exists
    if user:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=1)

        db.add(PasswordResetToken(
            user_id=user.user_id,
            token=token,
            expires_at=expires,
        ))
        db.commit()

        reset_link = f"https://alkohout.github.io/food_body_connection/reset-password.html?token={token}"
        try:
            send_reset_email(user.email, reset_link)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")

    return {"message": "If your email is registered you will receive a reset link shortly."}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    record = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == body.token)
        .first()
    )

    if not record or record.used or record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired.")

    user = db.query(User).filter(User.user_id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")

    user.password_hash = hash_password(body.new_password)
    record.used = True
    db.commit()

    return {"message": "Password updated successfully."}




