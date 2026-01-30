"""Script to create database tables for job-agent application."""

import os
import sys
from pathlib import Path

# Add project root to Python path if running directly
# This allows the script to work both as a module and when run directly
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.database.session import Base, engine

# Import all models to ensure they're registered with Base.metadata
from src.database.models import (
    Run,
    JobSearch,
    JobPosting,
    MatchedJob,
    UserProfile,
    CompanyResearch,
    CoverLetter,
    Artifact,
)


def create_tables(overwrite: bool = False):
    """Create all tables defined in the models.

    Args:
        overwrite: If True, drop existing tables before creating new ones.
                  If False (default), only create tables that don't exist (idempotent).

    This function will create all tables that are registered with Base.metadata.
    By default, it's idempotent - running it multiple times won't recreate existing tables.
    """
    # Print all tables that will be created
    print("Tables to be created:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")

    # Check if tables already exist
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    tables_to_create = list(Base.metadata.tables.keys())
    existing_in_models = [t for t in tables_to_create if t in existing_tables]

    if existing_in_models:
        print(f"\n⚠️  Found {len(existing_in_models)} existing table(s):")
        for table in existing_in_models:
            print(f"  - {table}")

        if overwrite:
            print("\n⚠️  OVERWRITE MODE: Dropping existing tables...")
            Base.metadata.drop_all(
                bind=engine,
                tables=[Base.metadata.tables[t] for t in existing_in_models],
            )
            print("✓ Existing tables dropped")
        else:
            print(
                "\n⚠️  Tables already exist. Use --overwrite flag to drop and recreate them."
            )
            print("   (Current run will only create missing tables)")

    print("\nCreating database tables...")

    # Create the tables
    Base.metadata.create_all(bind=engine)

    # Add Run.user_profile_id if runs table exists but column is missing (existing DBs)
    from sqlalchemy import text

    inspector_after = inspect(engine)
    if "runs" in inspector_after.get_table_names():
        run_columns = [c["name"] for c in inspector_after.get_columns("runs")]
        if "user_profile_id" not in run_columns:
            print("Adding user_profile_id to runs table...")
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN user_profile_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL"
                    )
                )
                conn.commit()
            print("✓ user_profile_id column added to runs")

    print("✓ Tables created successfully!")
    print("\nYou can now:")
    print("  1. Connect to the database using TablePlus or psql")
    print("  2. Use the repository pattern to perform CRUD operations")
    print("  3. Integrate database operations into your workflow")


if __name__ == "__main__":
    # Check for --overwrite flag or OVERWRITE_TABLES environment variable
    overwrite = False

    # Check command line arguments
    if "--overwrite" in sys.argv or "-o" in sys.argv:
        overwrite = True

    # Check environment variable
    if os.getenv("OVERWRITE_TABLES", "").lower() in ("true", "1", "yes"):
        overwrite = True

    create_tables(overwrite=overwrite)
