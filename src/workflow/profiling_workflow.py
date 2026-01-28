"""Profiling workflow orchestrator."""

import logging

from src.workflow.base_workflow import BaseWorkflow
from src.workflow.profiling_context import ProfilingWorkflowContext
from src.workflow.nodes.user_input_node import UserInputNode
from src.workflow.nodes.cv_processing_node import CVProcessingNode

logger = logging.getLogger(__name__)


class ProfilingWorkflow(BaseWorkflow):
    """Workflow orchestrator for user profiling pipeline.
    
    This workflow processes user input and CV/PDF documents to create
    a structured user profile that is saved to the database.
    
    The workflow consists of:
    1. UserInputNode - Validates user input (name, email, basic info)
    2. CVProcessingNode - Processes CV/PDF, uses AI to structure profile, saves to DB
    """
    
    class Context(ProfilingWorkflowContext):
        """Workflow-specific context with additional validations."""
        pass
    
    def __init__(self):
        """Initialize the workflow with nodes."""
        super().__init__(workflow_type="profiling")
        
        # Initialize nodes
        self.user_input_node = UserInputNode()
        self.cv_processing_node = CVProcessingNode()
    
    async def run(self, context: Context) -> Context:
        """Execute the profiling workflow.
        
        Args:
            context: The workflow context with user input and PDF paths
            
        Returns:
            Updated context with profile information
        """
        self.logger.info("Starting profiling workflow")
        
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
        
        try:
            # Step 1: Validate user input
            context = await self._execute_node(self.user_input_node, context)
            if context.has_errors():
                self.logger.warning("User input validation failed, stopping workflow")
                return context
            
            # Step 2: Process CV and build profile
            context = await self._execute_node(self.cv_processing_node, context)
            
        finally:
            # Update execution record as completed
            if execution_id:
                final_status = "failed" if context.has_errors() else "completed"
                self._update_workflow_execution(
                    context,
                    status=final_status,
                )
        
        self.logger.info("Profiling workflow completed")
        self.logger.info(f"Execution path: {' -> '.join(self.get_execution_path())}")
        return context
