"""
Database session management.

One transaction per request: commit on success, rollback on any exception.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=settings.debug,
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.debug,
    )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: yields a DB session scoped to the request.
    Commits on clean exit, rolls back on exception.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
