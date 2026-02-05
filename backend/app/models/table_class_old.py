# backend/app/models/table_class.py

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    allergen_log = relationship("AllergenLog", back_populates="user", cascade="all, delete-orphan")
    symptom_log = relationship("SymptomLog", back_populates="user", cascade="all, delete-orphan")

class Allergen(Base):
    __tablename__ = 'allergen'
    
    allergen_id = Column(Integer, primary_key=True)
    allergen_name = Column(String(255), nullable=False)
    
    # Relationships
    allergen_log = relationship("AllergenLog", back_populates="allergen", cascade="all, delete-orphan")

class Unit(Base):
    __tablename__ = 'unit'
    
    unit_id = Column(Integer, primary_key=True)
    unit_name = Column(String(100), nullable=False)
    unit_conversion = Column(Integer, nullable=False)  
    
    # Relationships
    allergen_log = relationship("AllergenLog", back_populates="unit")

class Symptom(Base):
    __tablename__ = 'symptom'
    
    symptom_id = Column(Integer, primary_key=True)
    symptom_name = Column(String(255), nullable=False)
    symptom_group = Column(String(255), nullable=True)
    
    # Relationships
    symptom_log = relationship("SymptomLog", back_populates="symptom", cascade="all, delete-orphan")

class AllergenLog(Base):
    __tablename__ = 'allergen_log'
    
    allergen_log_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    date_time = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)) 
    allergen_id = Column(Integer, ForeignKey('allergen.allergen_id'), nullable=False)
    quantity = Column(Float, nullable=True)
    unit_id = Column(Integer, ForeignKey('unit.unit_id'), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="allergen_log")
    allergen = relationship("Allergen", back_populates="allergen_log")
    unit = relationship("Unit", back_populates="allergen_log")

class SymptomLog(Base):
    __tablename__ = 'symptom_log'
    
    symptom_log_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    date_time = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    symptom_id = Column(Integer, ForeignKey('symptom.symptom_id'), nullable=False)
    symptom_intensity = Column(Integer, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="symptom_log")
    symptom = relationship("Symptom", back_populates="symptom_log")
    
    # Add check constraint for symptom_intensity
    __table_args__ = (
        CheckConstraint('symptom_intensity >= 0 AND symptom_intensity <= 3', 
                       name='check_symptom_intensity_range'),
    )
