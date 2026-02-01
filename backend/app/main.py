# app/main.py
from fastapi import FastAPI, Response
from app.database import engine, Base
from app.api.routes.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
import app.api.routes.allergens as allergens
import app.api.routes.symptoms as symptoms 
import app.api.routes.symptom_groups as symptom_groups 
import app.api.routes.analysis as analysis
import app.api.routes.intensity_volume as intensity_volume
import app.api.routes.plot_eda as plot_eda  
import app.api.routes.stats_report as stats_report  
import app.api.routes.temporal_stats as temporal_stats
import app.api.routes.symptom_group_histogram as symptom_group_histogram
import app.api.routes.predict as predict
import app.api.routes.plot_allergen_rank as plot_allergen_rank
import app.api.routes.plot_time_series as plot_time_series
import app.api.routes.plot_bar_plots as plot_bar_plots
import app.api.routes.plot_risk as plot_risk
import app.api.routes.generate_summary_text as generate_summary_text 
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
app.include_router(symptom_groups.router)
app.include_router(units.router)
app.include_router(entries.router)
app.include_router(analysis.router)
app.include_router(intensity_volume.router)
app.include_router(plot_eda.router)
app.include_router(stats_report.router)
app.include_router(temporal_stats.router)
app.include_router(symptom_group_histogram.router)
app.include_router(predict.router)
app.include_router(plot_allergen_rank.router)
app.include_router(plot_time_series.router)
app.include_router(plot_bar_plots.router)
app.include_router(plot_risk.router)
app.include_router(generate_summary_text.router)

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



