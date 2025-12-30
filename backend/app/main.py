# app/main.py
from fastapi import FastAPI
from app.database import engine, Base
from app.api.routes.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
import app.api.routes.allergens as allergens
import app.api.routes.symptoms as symptoms 
from app.api.routes import units
from app.api.routes import entries

app = FastAPI(title="Food–Body Connection API")

origins = [
    "https://alkohout.github.io",
    "http://localhost:5500", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(allergens.router)
app.include_router(symptoms.router)
app.include_router(units.router)
app.include_router(entries.router)

# Create tables (temporary — later use migrations)
Base.metadata.create_all(bind=engine)

@app.get("/")
def health_check():
    return {"status": "ok"}

from sqlalchemy import text
from app.database import SessionLocal

@app.get("/db-test")
def db_test():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"db": "connected"}
    finally:
        db.close()

@app.post("/__sanity_check")
def sanity_check():
    return {"status": "post works"}



