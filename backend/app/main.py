# app/main.py
from fastapi import FastAPI, Response
from app.database import engine, Base
from app.api.routes.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
import app.api.routes.allergens as allergens
import app.api.routes.symptoms as symptoms 
import app.api.routes.analysis as analysis
import app.api.routes.intensity_volume as intensity_volume
import app.api.routes.plot_eda as plot_eda  
from app.api.routes import units
from app.api.routes import entries
import base64

app = FastAPI(title="Food–Body Connection API")

# A tiny 16x16 transparent PNG (1x1 pixel)
favicon_base64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
)

@app.get("/favicon.ico")
async def favicon():
    favicon_bytes = base64.b64decode(favicon_base64)
    return Response(content=favicon_bytes, media_type="image/png")

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
app.include_router(analysis.router)
app.include_router(intensity_volume.router)
app.include_router(plot_eda.router)

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



