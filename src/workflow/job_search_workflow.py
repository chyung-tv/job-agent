"""Job search workflow orchestrator."""

import uuid
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.workflow.base_context import JobSearchWorkflowContext
from src.workflow.nodes.discovery_node import DiscoveryNode
from src.workflow.nodes.profiling_node import ProfilingNode
from src.workflow.nodes.matching_node import MatchingNode
from src.workflow.nodes.research_node import ResearchNode
from src.workflow.nodes.fabrication_node import FabricationNode
from src.workflow.nodes.completion_node import CompletionNode
from src.workflow.nodes.delivery_node import DeliveryNode
from src.database import db_session, GenericRepository, Run, WorkflowExecution

logger = logging.getLogger(__name__)


class JobSearchWorkflow:
    """Workflow orchestrator for job search pipeline."""
    
    class Context(JobSearchWorkflowContext):
        """Workflow-specific context with additional validations."""
        pass
    
    def __init__(self):
        """Initialize the workflow with nodes."""
        self.nodes = [
            DiscoveryNode(),
            ProfilingNode(),
            MatchingNode(),
            ResearchNode(),
            FabricationNode(),
            CompletionNode(),
            DeliveryNode(),
        ]
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def _create_run(self, context: Context) -> uuid.UUID:
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
    
    def _log_workflow_start(self, context: Context) -> uuid.UUID:
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
                workflow_type="job_search",
                status="processing",
                context_snapshot=json.loads(context.model_dump_json()),
                started_at=datetime.utcnow(),
            )
            session.add(execution)
            session.commit()
            session.refresh(execution)
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
        execution_id: uuid.UUID,
        context: Context,
        current_node: Optional[str] = None,
        status: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update workflow execution record.
        
        Args:
            execution_id: WorkflowExecution ID
            context: The workflow context
            current_node: Name of current node
            status: Execution status
            error_message: Error message if any
        """
        session_gen = db_session()
        session = next(session_gen)
        try:
            execution = session.query(WorkflowExecution).filter_by(id=execution_id).first()
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
    
    async def run(self, context: Context) -> Context:
        """Execute the workflow with all nodes.
        
        Args:
            context: The workflow context with input parameters
            
        Returns:
            Updated context with results
        """
        self.logger.info("Starting job search workflow")
        
        # Create run_id if not present
        if not context.run_id:
            try:
                self._create_run(context)
            except Exception as e:
                context.add_error(f"Failed to create run: {e}")
                self.logger.error(f"Failed to create run: {e}")
                return context
        
        # Log workflow start
        execution_id = None
        try:
            execution_id = self._log_workflow_start(context)
        except Exception as e:
            self.logger.warning(f"Failed to log workflow start: {e}")
            # Continue execution even if logging fails
        
        # Execute nodes sequentially
        for i, node in enumerate(self.nodes):
            node_name = node.__class__.__name__
            self.logger.info(f"Executing node {i+1}/{len(self.nodes)}: {node_name}")
            
            try:
                # Update execution record with current node
                if execution_id:
                    self._update_workflow_execution(execution_id, context, current_node=node_name)
                
                # Execute node
                context = await node.run(context)
                
                # Log errors if any
                if context.has_errors():
                    self.logger.warning(f"Node {node_name} completed with errors: {context.errors}")
                
            except Exception as e:
                error_msg = f"Node {node_name} failed: {e}"
                self.logger.error(error_msg)
                context.add_error(error_msg)
                
                # Update execution record with error
                if execution_id:
                    self._update_workflow_execution(
                        execution_id,
                        context,
                        current_node=node_name,
                        status="failed",
                        error_message=error_msg,
                    )
                
                # Continue execution (simple error handling for now)
                continue
        
        # Update execution record as completed
        if execution_id:
            final_status = "failed" if context.has_errors() else "completed"
            self._update_workflow_execution(
                execution_id,
                context,
                status=final_status,
            )
        
        self.logger.info("Job search workflow completed")
        return context
