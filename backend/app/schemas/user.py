# app/schemas/user.py
from pydantic import BaseModel, EmailStr, constr

class UserCreate(BaseModel):
    email: EmailStr
    password: constr(max_length=72)  # enforce bcrypt limit

class UserOut(BaseModel):
    user_id: int
    email: EmailStr

    class Config:
        from_attributes = True

