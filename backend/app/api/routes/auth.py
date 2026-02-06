# app/api/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import User
from app.schemas.user import UserCreate, UserOut
from app.core.security import hash_password, verify_password
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from app.core.jwt import create_access_token, SECRET_KEY, ALGORITHM
from app.models.table_class import User, Allergen, Symptom
from jose import JWTError, jwt

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@router.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check email
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 1. Create the user
    new_user = User(
        email=user.email,
        password_hash=hash_password(user.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # ----------------------------------------------------
    # 2. Clone seed symptoms & allergens to the new user
    # ----------------------------------------------------

    # Determine which user is the "seed template" user
    # You can change this ID depending on your seed_data.py setup
    SEED_USER_EMAIL = "seed@data.com"   # recommended seed template
    seed_user = db.query(User).filter(User.email == SEED_USER_EMAIL).first()

    if not seed_user:
        raise HTTPException(
            status_code=500,
            detail="Seed user not found; run seed_data.py first"
        )

    # Fetch all symptoms for seed user
    seed_symptoms = db.query(Symptom).filter(
        Symptom.user_id == seed_user.user_id
    ).all()

    # Fetch all allergens for seed user
    seed_allergens = db.query(Allergen).filter(
        Allergen.user_id == seed_user.user_id
    ).all()

    # Clone symptoms
    for s in seed_symptoms:
        db.add(Symptom(
            symptom_name=s.symptom_name,
            symptom_group=s.symptom_group,
            user_id=new_user.user_id
        ))

    # Clone allergens
    for a in seed_allergens:
        db.add(Allergen(
            allergen_name=a.allergen_name,
            user_id=new_user.user_id
        ))

    db.commit()

    return new_user


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": str(user.user_id), "email": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.user_id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

# Example protected route
@router.get("/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user




