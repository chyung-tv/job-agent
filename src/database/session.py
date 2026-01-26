"""SQLAlchemy session management and base model configuration."""

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from src.database.database_utils import DatabaseUtils

# Create engine (connection pool)
engine = create_engine(DatabaseUtils.get_connection_string())

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,  # Don't auto-commit (we control transactions)
    autoflush=False,   # Don't auto-flush (we control when to sync)
    bind=engine        # Use this engine
)

# Create base class for models
Base = declarative_base()


def db_session() -> Generator[Session, None, None]:
    """Database Session Dependency.
    
    Provides a database session with automatic commit/rollback.
    
    Yields:
        SQLAlchemy Session instance
        
    Example:
        ```python
        session = next(db_session())
        try:
            # Use session here
            session.commit()
        finally:
            session.close()
        ```
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()  # Commit if no errors
    except Exception as ex:
        session.rollback()  # Rollback on error
        logging.error(f"Database session error: {ex}")
        raise ex
    finally:
        session.close()  # Always close
