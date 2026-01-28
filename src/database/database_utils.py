"""Database utility functions for connection management."""

import os
from dotenv import load_dotenv

load_dotenv()


class DatabaseUtils:
    """Utility class for database connection configuration."""

    @staticmethod
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
