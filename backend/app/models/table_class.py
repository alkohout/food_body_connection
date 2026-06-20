# backend/app/models/table_class.py

from sqlalchemy import Column, Integer, SmallInteger, String, Float, DateTime, Date, ForeignKey, CheckConstraint, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint
from datetime import datetime, timezone
from app.database import Base
from app.core.encryption import EncryptedString

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    allergen_log = relationship("AllergenLog", back_populates="user", cascade="all, delete-orphan")
    symptom_log = relationship("SymptomLog", back_populates="user", cascade="all, delete-orphan")
    allergen = relationship("Allergen",back_populates="user", cascade="all, delete-orphan")
    symptom = relationship("Symptom",back_populates="user", cascade="all, delete-orphan")
    medication = relationship("Medication", back_populates="user", cascade="all, delete-orphan")
    medication_regimen = relationship("MedicationRegimen", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("UserDocument", back_populates="user", cascade="all, delete-orphan")
    checkins = relationship("DailyCheckin", back_populates="user", cascade="all, delete-orphan")

class Allergen(Base):
    __tablename__ = 'allergen'
    
    allergen_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'),nullable=False)
    allergen_name = Column(EncryptedString, nullable=False)
    
    # Relationships
    allergen_log = relationship("AllergenLog", back_populates="allergen", cascade="all, delete-orphan")
    user = relationship("User", back_populates="allergen")

    __table_args__ = (
        UniqueConstraint('user_id', 'allergen_name', name='uq_user_allergen'),
    )


class Unit(Base):
    __tablename__ = 'unit'
    
    unit_id = Column(Integer, primary_key=True)
    unit_name = Column(String(100), nullable=False, unique=True)
    unit_conversion = Column(Integer, nullable=False)  
    
    # Relationships
    allergen_log = relationship("AllergenLog", back_populates="unit")

class Symptom(Base):
    __tablename__ = 'symptom'
    
    symptom_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'),nullable=False)
    symptom_name = Column(EncryptedString, nullable=False)
    symptom_group = Column(EncryptedString, nullable=True)
    
    # Relationships
    symptom_log = relationship("SymptomLog", back_populates="symptom", cascade="all, delete-orphan")
    user = relationship("User", back_populates="symptom")

    __table_args__ = (
        UniqueConstraint('user_id', 'symptom_name', name='uq_user_symptom'),
    )


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


class Medication(Base):
    __tablename__ = 'medication'

    medication_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    medication_name = Column(EncryptedString, nullable=False)

    user = relationship("User", back_populates="medication")
    regimens = relationship("MedicationRegimen", back_populates="medication", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('user_id', 'medication_name', name='uq_user_medication'),
    )


class MedicationRegimen(Base):
    __tablename__ = 'medication_regimen'

    regimen_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    medication_id = Column(Integer, ForeignKey('medication.medication_id'), nullable=False)
    dose = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False, default='mg')
    note = Column(EncryptedString, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)       # null = currently active

    user = relationship("User", back_populates="medication_regimen")
    medication = relationship("Medication", back_populates="regimens")


class PasswordResetToken(Base):
    __tablename__ = 'password_reset_token'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False, nullable=False)


class UserDocument(Base):
    __tablename__ = 'user_document'

    document_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    filename = Column(EncryptedString, nullable=False)
    description = Column(EncryptedString, nullable=True)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(EncryptedString, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="documents")


class DailyCheckin(Base):
    __tablename__ = 'daily_checkin'

    checkin_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    checkin_date = Column(Date, nullable=False)
    period = Column(String(10), nullable=False)  # 'morning' or 'evening'

    # General variables (all users)
    mood    = Column(SmallInteger, nullable=True)
    sleep   = Column(SmallInteger, nullable=True)   # morning only
    fatigue = Column(SmallInteger, nullable=True)
    gut     = Column(SmallInteger, nullable=True)
    stress  = Column(SmallInteger, nullable=True)

    # Extended variables (user 4)
    headache             = Column(SmallInteger, nullable=True)
    headache_overnight   = Column(SmallInteger, nullable=True)  # morning only
    brain_fog            = Column(SmallInteger, nullable=True)
    tinnitus             = Column(SmallInteger, nullable=True)
    visual_disturbance   = Column(SmallInteger, nullable=True)
    training             = Column(SmallInteger, nullable=True)  # morning only; 0=none 1=partial 2=full
    virus                = Column(SmallInteger, nullable=True)  # 0=none 1=mild 2=bad

    checkin_datetime = Column(DateTime(timezone=True), nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="checkins")

    __table_args__ = (
        UniqueConstraint('user_id', 'checkin_date', 'period', name='uq_user_checkin_date_period'),
        CheckConstraint("period IN ('morning', 'evening')", name='check_checkin_period'),
    )
