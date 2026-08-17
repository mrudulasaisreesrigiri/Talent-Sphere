from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL or "sqlite:///./talent_sphere_elevate.db"

# Try primary DB URL first; if MySQL is offline, fall back to SQLite seamlessly
try:
    if db_url.startswith("sqlite"):
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(db_url, pool_pre_ping=True)
        # Test connection
        conn = engine.connect()
        conn.close()
except Exception as e:
    logger.warning(f"Could not connect to primary database '{db_url}': {e}. Falling back to local SQLite database.")
    fallback_url = "sqlite:///./talent_sphere_elevate.db"
    engine = create_engine(fallback_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
