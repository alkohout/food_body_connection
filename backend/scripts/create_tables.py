from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect
from dotenv import load_dotenv
import os as os 
from app.database import Base
from app.models.table_class import User, AllergenLog, SymptomLog

# Load environment variables from .env file 
load_dotenv()

# Database connection setup
DATABASE_URL = os.getenv("DB_MAINT_URL")
engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")

# Delete database and Create a new database
DB_NAME = "foodbodyconnection"
with engine.connect() as conn:
    # Terminate any connections to the target DB
    conn.execute(
        text(f"""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '{DB_NAME}';
        """)
    )
    conn.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME}"))
    conn.execute(text(f"CREATE DATABASE {DB_NAME}"))

print(f"Database {DB_NAME} dropped and created successfully.")

# Create all tables
# Database connection setup
DATABASE_URL = os.getenv("DB_URL")
engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
Base.metadata.create_all(engine)

inspector = inspect(engine)
print(f"Database tables created:")
print(inspector.get_table_names())

