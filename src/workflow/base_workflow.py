"""Base workflow class for flexible workflow orchestration."""

import uuid
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from src.database import db_session, Run
from src.langfuse_utils import (
    create_workflow_trace_context,
    observe,
    propagate_attributes,
)

if TYPE_CHECKING:
    from src.workflow.base_context import BaseContext

logger = logging.getLogger(__name__)


class ExecutionRecord:
    """Record of a single node execution."""

    def __init__(
        self,
        node_name: str,
        timestamp: datetime,
        success: bool,
        error: Optional[str] = None,
    ):
        self.node_name = node_name
        self.timestamp = timestamp
        self.success = success
        self.error = error

    def __repr__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"{status} {self.node_name} @ {self.timestamp.isoformat()}"


class BaseWorkflow(ABC):
    """Base class for all workflows providing common functionality.

    This class handles:
    - Database logging and tracking (run creation when context has no run_id)
    - Node execution with error handling
    - Execution history tracking
    - Workflow lifecycle management

    Status updates for the run are done by Celery tasks via update_run_status.
    """

    def __init__(self, workflow_type: str = "generic"):
        """Initialize the base workflow.

        Args:
            workflow_type: Type identifier for the workflow (e.g., "job_search")
        """
        self.workflow_type = workflow_type
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.execution_history: List[ExecutionRecord] = []

    def _create_run(self, context: "BaseContext") -> uuid.UUID:
        """Create a new run record in the database.

        Args:
            context: The workflow context

        Returns:
            Created run ID
        """
        session_gen = db_session()
        session = next(session_gen)
        try:
            user_id = getattr(context, "user_id", None)
            run = Run(status="processing", user_id=user_id)
            session.add(run)
            session.commit()
            session.refresh(run)
            context.run_id = run.id
            self.logger.info(f"Created run with ID: {run.id}")
            return run.id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to create run: {e}")
            raise
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass

    async def _execute_node(
        self,
        node: Any,  # BaseNode, but avoiding circular import
        context: "BaseContext",
        update_db: bool = True,
    ) -> "BaseContext":
        """Execute a single node with error handling and tracking.

        Args:
            node: The node to execute
            context: The workflow context
            update_db: Unused; kept for API compatibility. Status updates are in Celery tasks.

        Returns:
            Updated context after node execution
        """
        node_name = node.__class__.__name__
        self.logger.info(f"Executing node: {node_name}")

        try:
            # Execute node
            context = await node.run(context)

            # Record successful execution
            self.execution_history.append(
                ExecutionRecord(
                    node_name=node_name,
                    timestamp=datetime.utcnow(),
                    success=True,
                )
            )

            # Log errors if any
            if context.has_errors():
                self.logger.warning(
                    f"Node {node_name} completed with errors: {context.errors}"
                )

            return context

        except Exception as e:
            error_msg = f"Node {node_name} failed: {e}"
            self.logger.error(error_msg)
            context.add_error(error_msg)

            # Record failed execution
            self.execution_history.append(
                ExecutionRecord(
                    node_name=node_name,
                    timestamp=datetime.utcnow(),
                    success=False,
                    error=str(e),
                )
            )

            # Re-raise to allow caller to handle
            raise

    def get_execution_path(self) -> List[str]:
        """Get the execution path as a list of node names.

        Returns:
            List of node names in execution order
        """
        return [record.node_name for record in self.execution_history]

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the workflow execution.

        Returns:
            Dictionary with execution summary
        """
        successful_nodes = [r.node_name for r in self.execution_history if r.success]
        failed_nodes = [r.node_name for r in self.execution_history if not r.success]

        return {
            "workflow_type": self.workflow_type,
            "total_nodes_executed": len(self.execution_history),
            "successful_nodes": successful_nodes,
            "failed_nodes": failed_nodes,
            "execution_path": self.get_execution_path(),
        }

    @observe()
    async def run(self, context: "BaseContext") -> "BaseContext":
        """Execute the workflow with tracing and lifecycle; delegates to _execute().

        Subclasses implement _execute() with their specific node flow.
        """
        trace_context = create_workflow_trace_context(
            run_id=str(context.run_id) if context.run_id else None,
            workflow_type=self.workflow_type,
            metadata={"workflow_class": self.__class__.__name__},
        )
        with propagate_attributes(**trace_context):
            self.logger.info(f"Starting {self.workflow_type} workflow")
            if not context.run_id:
                try:
                    self._create_run(context)
                except Exception as e:
                    context.add_error(f"Failed to create run: {e}")
                    self.logger.error("Failed to create run: %s", e)
                    return context
            result = context
            try:
                result = await self._execute(context)
            except Exception as e:
                self.logger.error("Workflow execution failed: %s", e, exc_info=True)
                raise
            return result

    @abstractmethod
    async def _execute(self, context: "BaseContext") -> "BaseContext":
        """Execute workflow-specific logic (node flow). Subclasses implement this."""
        pass
