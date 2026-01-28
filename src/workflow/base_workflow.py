"""Base workflow class for flexible workflow orchestration."""

import uuid
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy.orm import Session

from src.database import db_session, Run, WorkflowExecution

if TYPE_CHECKING:
    from src.workflow.base_context import BaseContext
    from src.workflow.base_node import BaseNode

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
    - Database logging and tracking (run creation, execution tracking)
    - Node execution with error handling
    - Execution history tracking
    - Workflow lifecycle management
    """

    def __init__(self, workflow_type: str = "generic"):
        """Initialize the base workflow.

        Args:
            workflow_type: Type identifier for the workflow (e.g., "job_search")
        """
        self.workflow_type = workflow_type
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.execution_history: List[ExecutionRecord] = []
        self._execution_id: Optional[uuid.UUID] = None

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
            run = Run(status="processing")
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

    def _log_workflow_start(self, context: "BaseContext") -> uuid.UUID:
        """Log workflow execution start.

        Args:
            context: The workflow context

        Returns:
            WorkflowExecution ID
        """
        session_gen = db_session()
        session = next(session_gen)
        try:
            execution = WorkflowExecution(
                run_id=context.run_id,
                workflow_type=self.workflow_type,
                status="processing",
                context_snapshot=json.loads(context.model_dump_json()),
                started_at=datetime.utcnow(),
            )
            session.add(execution)
            session.commit()
            session.refresh(execution)
            self._execution_id = execution.id
            self.logger.info(f"Created workflow execution record: {execution.id}")
            return execution.id
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to log workflow start: {e}")
            raise
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass

    def _update_workflow_execution(
        self,
        context: "BaseContext",
        current_node: Optional[str] = None,
        status: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update workflow execution record.

        Args:
            context: The workflow context
            current_node: Name of current node
            status: Execution status
            error_message: Error message if any
        """
        if not self._execution_id:
            return

        session_gen = db_session()
        session = next(session_gen)
        try:
            execution = (
                session.query(WorkflowExecution)
                .filter_by(id=self._execution_id)
                .first()
            )
            if execution:
                execution.context_snapshot = json.loads(context.model_dump_json())
                if current_node:
                    execution.current_node = current_node
                if status:
                    execution.status = status
                if error_message:
                    execution.error_message = error_message
                if status == "completed" or status == "failed":
                    execution.completed_at = datetime.utcnow()
                execution.updated_at = datetime.utcnow()
                session.commit()
        except Exception as e:
            self.logger.warning(f"Failed to update workflow execution: {e}")
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
            update_db: Whether to update database execution record

        Returns:
            Updated context after node execution
        """
        node_name = node.__class__.__name__
        self.logger.info(f"Executing node: {node_name}")

        # Update execution record with current node
        if update_db and self._execution_id:
            self._update_workflow_execution(context, current_node=node_name)

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

            # Update execution record with error
            if update_db and self._execution_id:
                self._update_workflow_execution(
                    context,
                    current_node=node_name,
                    status="failed",
                    error_message=error_msg,
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
            "execution_id": str(self._execution_id) if self._execution_id else None,
        }

    @abstractmethod
    async def run(self, context: "BaseContext") -> "BaseContext":
        """Execute the workflow with custom logic.

        Subclasses must implement this method to define their specific workflow flow.
        Use _execute_node() to execute individual nodes with proper tracking.

        Args:
            context: The workflow context with input parameters

        Returns:
            Updated context with results
        """
        pass
