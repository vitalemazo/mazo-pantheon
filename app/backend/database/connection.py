from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Get the backend directory path
BACKEND_DIR = Path(__file__).parent.parent
DATABASE_PATH = BACKEND_DIR / "hedge_fund.db"

# Database configuration - prefer PostgreSQL from environment, fallback to SQLite
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
    # Using PostgreSQL
    logger.info(f"Using PostgreSQL database")
    engine = create_engine(DATABASE_URL)
else:
    # Fallback to SQLite for local development
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
    logger.info(f"Using SQLite database: {DATABASE_PATH}")
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}  # Needed for SQLite
    )

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 