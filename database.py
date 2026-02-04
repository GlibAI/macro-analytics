"""
Database configuration and session management for PostgreSQL
"""

import os
import logging
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()
logger.debug("Environment variables loaded from .env file")

DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "")
DB_NAME = os.getenv("DB_NAME", "")

logger.debug(f"Database config: host={DB_HOST}, port={DB_PORT}, db={DB_NAME}, user={DB_USER}")

if DB_PASSWORD:
    encoded_password = quote_plus(DB_PASSWORD)
    DATABASE_URL = (
        f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
else:
    DATABASE_URL = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

logger.debug("Creating SQLAlchemy engine...")
engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
)
logger.info("SQLAlchemy engine created successfully")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
logger.debug("SessionLocal factory configured")

Base = declarative_base()


def get_db():
    """
    Dependency function to get database session.
    Use this in FastAPI endpoints to get a database connection.
    """
    logger.debug("Creating new database session")
    db = SessionLocal()
    try:
        yield db
    finally:
        logger.debug("Closing database session")
        db.close()


def init_db():
    """
    Initialize the database by creating all tables.
    Call this function when starting your application.
    """
    logger.info("Initializing database - creating tables if they don't exist")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization complete")
