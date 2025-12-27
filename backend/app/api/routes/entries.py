# app/api/routes/entries.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.schemas.entry import AllergenEntryCreate
from app.models.table_class import AllergenLog
