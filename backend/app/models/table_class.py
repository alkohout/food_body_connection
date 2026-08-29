# backend/app/models/table_class.py

from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, CheckConstraint, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint
from datetime import datetime, timezone
from app.database import Base
from app.core.encryption import EncryptedString, EncryptedInt

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
    exercises = relationship("Exercise", back_populates="user", cascade="all, delete-orphan")
    workout_sessions = relationship("WorkoutSession", back_populates="user", cascade="all, delete-orphan")
    set_logs = relationship("SetLog", back_populates="user", cascade="all, delete-orphan")
    training_profile = relationship("TrainingProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    practice_items = relationship("PracticeItem", back_populates="user", cascade="all, delete-orphan")

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

    # General variables (all users) — stored encrypted as Text
    mood    = Column(EncryptedInt, nullable=True)
    sleep   = Column(EncryptedInt, nullable=True)   # morning only
    fatigue = Column(EncryptedInt, nullable=True)
    gut     = Column(EncryptedInt, nullable=True)
    stress  = Column(EncryptedInt, nullable=True)

    # Extended variables (user 4) — stored encrypted as Text
    headache             = Column(EncryptedInt, nullable=True)
    headache_overnight   = Column(EncryptedInt, nullable=True)  # morning only
    brain_fog            = Column(EncryptedInt, nullable=True)
    tinnitus             = Column(EncryptedInt, nullable=True)
    visual_disturbance   = Column(EncryptedInt, nullable=True)
    training             = Column(EncryptedInt, nullable=True)  # morning only; 0=none 1=partial 2=full
    virus                = Column(EncryptedInt, nullable=True)  # 0=none 1=mild 2=bad

    checkin_datetime = Column(DateTime(timezone=True), nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="checkins")

    __table_args__ = (
        UniqueConstraint('user_id', 'checkin_date', 'period', name='uq_user_checkin_date_period'),
        CheckConstraint("period IN ('morning', 'evening')", name='check_checkin_period'),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Training
#
# Names are encrypted like every other user-supplied label in this file, so they
# cannot be grouped or filtered in SQL — aggregation happens in Python, as it
# does for allergens and symptoms. The classification columns below are plain
# text on purpose: they are a fixed vocabulary rather than user data, and the
# programme logic has to filter on them.
# ──────────────────────────────────────────────────────────────────────────────

class Exercise(Base):
    __tablename__ = 'exercise'

    exercise_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    exercise_name = Column(EncryptedString, nullable=False)

    # strength | mobility | martial | conditioning
    category = Column(String(30), nullable=False, default='strength')
    # knee | hip | core | upper | posterior | calf | whole
    target = Column(String(30), nullable=True)
    # bodyweight | dumbbell | barbell | band | tube | none
    equipment = Column(String(30), nullable=False, default='bodyweight')

    # Loaded one side at a time, so a set belongs to a side and both sides need
    # logging before the exercise is done.
    is_unilateral = Column(Boolean, nullable=False, default=False)
    # Held rather than repped, so reps are meaningless and hold_seconds is the
    # progression variable.
    is_isometric = Column(Boolean, nullable=False, default=False)

    # Requires standing on one leg. Not the same as unilateral: a lying quad
    # set is done one leg at a time and needs no balance at all, so a knee
    # that gives way is no reason to skip it.
    needs_balance = Column(Boolean, nullable=False, default=False)

    form_cues = Column(EncryptedString, nullable=True)
    video_url = Column(String(500), nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="exercises")
    set_logs = relationship("SetLog", back_populates="exercise", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('user_id', 'exercise_name', name='uq_user_exercise'),
    )


class WorkoutSession(Base):
    __tablename__ = 'workout_session'

    session_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    date_time = Column(DateTime(timezone=True), nullable=False,
                       default=lambda: datetime.now(timezone.utc))

    # strength | tai_chi | kung_fu | mixed | other — martial practice loads the
    # knees too, so leaving it out would make load management meaningless.
    session_type = Column(String(30), nullable=False, default='strength')
    duration_min = Column(Integer, nullable=True)
    overall_rpe = Column(Integer, nullable=True)
    notes = Column(EncryptedString, nullable=True)

    # Filled in the following day, not at the time. This is the input to the
    # back-off rule: knee pain that is worse 24h later means the last session
    # was too much, however it felt while training.
    next_day_knee = Column(Integer, nullable=True)

    user = relationship("User", back_populates="workout_sessions")
    sets = relationship("SetLog", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint('overall_rpe IS NULL OR (overall_rpe >= 1 AND overall_rpe <= 10)',
                        name='check_session_rpe_range'),
        CheckConstraint('next_day_knee IS NULL OR (next_day_knee >= 0 AND next_day_knee <= 10)',
                        name='check_next_day_knee_range'),
    )


class SetLog(Base):
    __tablename__ = 'set_log'

    set_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    session_id = Column(Integer, ForeignKey('workout_session.session_id'), nullable=False)
    exercise_id = Column(Integer, ForeignKey('exercise.exercise_id'), nullable=False)

    set_number = Column(Integer, nullable=False, default=1)
    reps = Column(Integer, nullable=True)
    # Total load moved, bar included, so it is comparable across sessions
    # without needing to know how the dumbbell was made up.
    weight_kg = Column(Float, nullable=True)
    # Band resistance rating rather than an actual force. Not interchangeable
    # with weight_kg, so it is kept in its own column instead of being faked
    # into one number.
    band_kg = Column(Float, nullable=True)
    hold_seconds = Column(Integer, nullable=True)
    side = Column(String(10), nullable=True)   # left | right | null

    rpe = Column(Integer, nullable=True)
    # Pain during the set, 0-10. The whole programme turns on this: it drives
    # the back-off rule and is what makes training comparable with the symptom
    # logs in the rest of the app.
    pain = Column(Integer, nullable=True)

    user = relationship("User", back_populates="set_logs")
    session = relationship("WorkoutSession", back_populates="sets")
    exercise = relationship("Exercise", back_populates="set_logs")

    __table_args__ = (
        CheckConstraint('rpe IS NULL OR (rpe >= 1 AND rpe <= 10)',
                        name='check_set_rpe_range'),
        CheckConstraint('pain IS NULL OR (pain >= 0 AND pain <= 10)',
                        name='check_set_pain_range'),
        CheckConstraint("side IS NULL OR side IN ('left', 'right')",
                        name='check_set_side'),
    )


class TrainingProfile(Base):
    __tablename__ = 'training_profile'

    profile_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, unique=True)

    # Which programme to follow. Plain text, not encrypted, because the
    # programme logic has to branch on it and a non-deterministic cipher cannot
    # be compared in SQL. It is a training preference, not a diagnosis.
    focus = Column(String(30), nullable=False, default="general")

    goals = Column(EncryptedString, nullable=True)
    constraints = Column(EncryptedString, nullable=True)

    # Bars are weighed, not assumed: spin-lock bars vary by a kilo or more and
    # every working load is quoted including the bar.
    dumbbell_bar_kg = Column(Float, nullable=True)
    barbell_bar_kg = Column(Float, nullable=True)
    # JSON: what plates and bands are actually owned, so the programme only
    # ever prescribes a load that can be built.
    equipment_json = Column(String, nullable=True)

    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="training_profile")


class PracticeItem(Base):
    """A user's own routine, bookending the prescribed strength work.

    The tai chi and kung fu that used to be hard-coded into one programme
    lives here instead, so anyone can build their own — yoga, a warm-up, a
    walk — without it being someone else's practice appended to their session.
    """
    __tablename__ = 'practice_item'

    practice_item_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    exercise_id = Column(Integer, ForeignKey('exercise.exercise_id'), nullable=False)

    slot = Column(String(10), nullable=False, default='before')   # before | after
    position = Column(Integer, nullable=False, default=0)

    # check = it either happened or it did not, which is most practice.
    scheme = Column(String(10), nullable=False, default='check')  # check | reps | iso
    sets = Column(Integer, nullable=False, default=1)
    low = Column(Integer, nullable=False, default=0)
    high = Column(Integer, nullable=False, default=0)

    # Two things done in turn — the 42 and 37 forms, or left and right routines.
    # Whichever was practised last, the other is due.
    alternates_with_id = Column(Integer, ForeignKey('exercise.exercise_id'), nullable=True)

    user = relationship("User", back_populates="practice_items")
    exercise = relationship("Exercise", foreign_keys=[exercise_id])
    alternate = relationship("Exercise", foreign_keys=[alternates_with_id])

    __table_args__ = (
        CheckConstraint("slot IN ('before', 'after')", name='check_practice_slot'),
        CheckConstraint("scheme IN ('check', 'reps', 'iso')", name='check_practice_scheme'),
    )
