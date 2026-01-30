"""Base node interface for workflow processing."""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.langfuse_utils import (
    create_workflow_trace_context,
    observe,
    propagate_attributes,
)

if TYPE_CHECKING:
    from src.workflow.base_context import BaseContext

logger = logging.getLogger(__name__)


class BaseNode(ABC):
    """Base class for all workflow nodes.

    Each node processes a context object, loads necessary data from the database,
    performs processing, persists results, and returns an updated context.
    """

    def __init__(self):
        """Initialize the node."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @observe()
    async def run(self, context: "BaseContext") -> "BaseContext":
        """Traced entry point; delegates to _execute(). Subclasses implement _execute()."""
        node_name = self.__class__.__name__
        trace_context = create_workflow_trace_context(
            execution_id=str(context.run_id)
            if getattr(context, "run_id", None)
            else None,
            run_id=str(context.run_id) if getattr(context, "run_id", None) else None,
            workflow_type=getattr(context, "workflow_type", None),
            node_name=node_name,
            metadata={"node_class": node_name},
        )
        with propagate_attributes(**trace_context):
            return await self._execute(context)

    @abstractmethod
    async def _execute(self, context: "BaseContext") -> "BaseContext":
        """Node-specific logic (validate, load, process, persist). Subclasses implement this."""
        pass

    def _get_db_session(self):
        """Helper to create database session.

        Returns:
            Database session generator
        """
        from src.database import db_session

        return db_session()

    def _load_data(self, context: "BaseContext", session) -> None:
        """Load heavy data from database based on context identifiers.

        Override in subclasses to load specific data needed by the node.
        This method is called before processing to ensure all necessary
        data is available.

        Args:
            context: The workflow context
            session: Database session
        """
        pass

    def _persist_data(self, context: "BaseContext", session) -> None:
        """Persist results to database.

        Override in subclasses to save node-specific results.
        This method is called after processing to save results.

        Args:
            context: The workflow context with results
            session: Database session
        """
        pass

    def _validate_context(self, context: "BaseContext") -> bool:
        """Validate required context fields before execution.

        Override in subclasses to check for required fields.
        If validation fails, errors should be added to context.errors.

        Args:
            context: The workflow context to validate

        Returns:
            True if valid, False otherwise
        """
        return True
