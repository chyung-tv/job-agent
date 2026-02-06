"""Run Alembic migrations programmatically.

This module provides a robust way to run migrations from setup.sh or other scripts,
avoiding the fragile one-liner approach that can fail in Docker containers.

Usage:
    python -m src.database.run_migrations          # upgrade to head
    python -m src.database.run_migrations --current  # show current revision
    python -m src.database.run_migrations --history  # show migration history
"""

import sys
from pathlib import Path

# Ensure project root is in path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command


def get_alembic_config() -> Config:
    """Get Alembic configuration from alembic.ini at project root."""
    ini_path = project_root / "alembic.ini"
    if not ini_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {ini_path}")
    return Config(str(ini_path))


def upgrade(revision: str = "head") -> None:
    """Upgrade database to a specific revision (default: head).
    
    Args:
        revision: Target revision identifier. Defaults to "head" for latest.
    """
    print(f"Running migrations: upgrade to {revision}")
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, revision)
    print("Migrations completed successfully.")


def downgrade(revision: str = "-1") -> None:
    """Downgrade database by a specific revision (default: one step back).
    
    Args:
        revision: Target revision identifier. Defaults to "-1" for one step back.
    """
    print(f"Running migrations: downgrade to {revision}")
    alembic_cfg = get_alembic_config()
    command.downgrade(alembic_cfg, revision)
    print("Downgrade completed successfully.")


def current() -> None:
    """Show current database revision."""
    print("Current database revision:")
    alembic_cfg = get_alembic_config()
    command.current(alembic_cfg, verbose=True)


def history() -> None:
    """Show migration history."""
    print("Migration history:")
    alembic_cfg = get_alembic_config()
    command.history(alembic_cfg, verbose=True)


def main() -> None:
    """CLI entry point for running migrations."""
    args = sys.argv[1:]
    
    if not args or args[0] in ("upgrade", "--upgrade", "-u"):
        # Default action: upgrade to head
        revision = args[1] if len(args) > 1 else "head"
        upgrade(revision)
    elif args[0] in ("--current", "-c", "current"):
        current()
    elif args[0] in ("--history", "-h", "history"):
        history()
    elif args[0] in ("downgrade", "--downgrade", "-d"):
        revision = args[1] if len(args) > 1 else "-1"
        downgrade(revision)
    else:
        print(f"Unknown argument: {args[0]}")
        print("Usage:")
        print("  python -m src.database.run_migrations          # upgrade to head")
        print("  python -m src.database.run_migrations upgrade [rev]  # upgrade to revision")
        print("  python -m src.database.run_migrations downgrade [rev]  # downgrade")
        print("  python -m src.database.run_migrations --current  # show current revision")
        print("  python -m src.database.run_migrations --history  # show history")
        sys.exit(1)


if __name__ == "__main__":
    main()
