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

    async def _execute(self, context: Context) -> Context:
        """Execute the profiling node flow (user input validation, CV processing)."""
        self.logger.info("Starting profiling workflow")

        # Step 1: Validate user input
        context = await self._execute_node(self.user_input_node, context)
        if context.has_errors():
            self.logger.warning("User input validation failed, stopping workflow")
            return context

        # Step 2: Process CV and build profile
        context = await self._execute_node(self.cv_processing_node, context)

        self.logger.info("Profiling workflow completed")
        self.logger.info("Execution path: %s", " -> ".join(self.get_execution_path()))
        return context
