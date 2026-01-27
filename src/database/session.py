"""SQLAlchemy session management and base model configuration."""

import os
import logging
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv()


def get_connection_string() -> str:
    """Get the SQLAlchemy connection string for PostgreSQL.
    
    CRITICAL: Uses postgresql+psycopg:// for psycopg3 (not postgresql://)
    - postgresql:// → SQLAlchemy tries psycopg2 (not installed)
    - postgresql+psycopg:// → SQLAlchemy uses psycopg (v3, installed)
    
    Returns:
        Connection string in format: postgresql+psycopg://user:pass@host:port/db
    """
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "job_agent")
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_password = os.getenv("POSTGRES_PASSWORD", "postgres")

    # CRITICAL: Use postgresql+psycopg:// for psycopg3
    # NOT postgresql:// (which defaults to psycopg2)
    return (
        f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )


# Create engine (connection pool)
engine = create_engine(get_connection_string())

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


@contextmanager
def with_db_session():
    """Context manager for database sessions.
    
    Automatically handles session lifecycle, commit, and rollback.
    
    Example:
        ```python
        with with_db_session() as session:
            # Use session here
            # Automatically commits on success, rolls back on error
        ```
    """
    session_gen = db_session()
    session = next(session_gen)
    try:
        yield session
    finally:
        try:
            next(session_gen, None)  # Consume generator to trigger commit/rollback
        except StopIteration:
            pass
