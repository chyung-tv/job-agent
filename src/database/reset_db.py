"""Reset the public schema (drop all tables) for a fresh migration run.

Used by ./setup.sh --overwrite. Run inside the api container so DB connection
uses the same env (POSTGRES_HOST=postgres, etc.). Destroys all data.
"""

from sqlalchemy import create_engine, text
from src.database.session import get_connection_string


def reset_public_schema() -> None:
    """Drop and re-create the public schema. All tables and data are removed."""
    import os
    engine = create_engine(get_connection_string())
    db_user = os.environ.get("POSTGRES_USER", "postgres")
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
        conn.execute(text(f"GRANT ALL ON SCHEMA public TO {db_user};"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        conn.commit()
    engine.dispose()


if __name__ == "__main__":
    reset_public_schema()
    print("Database public schema reset. Run: alembic upgrade head")
