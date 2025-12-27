# app/main.py
from fastapi import FastAPI
from app.database import engine, Base
from app.api.routes.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import entries  

app = FastAPI(title="Food–Body Connection API")

app.include_router(auth_router)
app.include_router(entries.router)

origins = [
    "https://alkohout.github.io",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://alkohout.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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



