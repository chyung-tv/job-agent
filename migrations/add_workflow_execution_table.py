"""Database migration to add WorkflowExecution table.

Run this script to add the WorkflowExecution table to your database.
"""

from src.database.models import Base, WorkflowExecution
from src.database.session import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_workflow_execution_table():
    """Create the WorkflowExecution table."""
    try:
        logger.info("Creating WorkflowExecution table...")
        WorkflowExecution.__table__.create(engine, checkfirst=True)
        logger.info("WorkflowExecution table created successfully")
    except Exception as e:
        logger.error(f"Failed to create WorkflowExecution table: {e}")
        raise


if __name__ == "__main__":
    create_workflow_execution_table()
