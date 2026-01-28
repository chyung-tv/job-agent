"""Job search workflow orchestrator."""

import logging
from typing import TYPE_CHECKING

from src.workflow.base_context import JobSearchWorkflowContext
from src.workflow.base_workflow import BaseWorkflow
from src.workflow.nodes.discovery_node import DiscoveryNode
from src.workflow.nodes.profile_retrieval_node import ProfileRetrievalNode
from src.workflow.nodes.matching_node import MatchingNode
from src.workflow.nodes.research_node import ResearchNode
from src.workflow.nodes.fabrication_node import FabricationNode
from src.workflow.nodes.completion_node import CompletionNode
from src.workflow.nodes.delivery_node import DeliveryNode

logger = logging.getLogger(__name__)


class JobSearchWorkflow(BaseWorkflow):
    """Workflow orchestrator for job search pipeline.
    
    This workflow provides flexible node execution with conditional routing.
    You can customize the flow by implementing custom logic in the run() method.
    
    Example:
        async def run(self, context: Context) -> Context:
            context = await self._execute_node(self.discovery_node, context)
            
            if context.has_errors():
                return context
            
            # Conditional routing based on context state
            if some_condition:
                context = await self._execute_node(self.nodeA, context)
            else:
                context = await self._execute_node(self.nodeB, context)
            
            return context
    """
    
    class Context(JobSearchWorkflowContext):
        """Workflow-specific context with additional validations."""
        pass
    
    def __init__(self):
        """Initialize the workflow with nodes."""
        super().__init__(workflow_type="job_search")
        
        # Initialize nodes as named attributes for easy access and conditional routing
        self.discovery_node = DiscoveryNode()
        self.profile_retrieval_node = ProfileRetrievalNode()
        self.matching_node = MatchingNode()
        self.research_node = ResearchNode()
        self.fabrication_node = FabricationNode()
        self.completion_node = CompletionNode()
        self.delivery_node = DeliveryNode()
    
    async def run(self, context: Context) -> Context:
        """Execute the workflow with flexible node execution.
        
        This method allows you to:
        - Execute nodes in any order
        - Add conditional logic based on context state
        - Route to different nodes based on conditions
        - Skip nodes when appropriate
        
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
        
        try:
            # Execute nodes with flexible flow
            # You can add conditional logic here based on context state
            
            # Step 1: Profile Retrieval - Load user profile from database
            # Note: Profile must be created first using ProfilingWorkflow
            context = await self._execute_node(self.profile_retrieval_node, context)
            if context.has_errors():
                self.logger.warning("Profile retrieval failed, stopping workflow")
                return context
            
            # Step 2: Discovery - Find jobs
            context = await self._execute_node(self.discovery_node, context)
            if context.has_errors():
                self.logger.warning("Discovery failed, stopping workflow")
                return context
            
            # Step 3: Matching - Match jobs against profile
            context = await self._execute_node(self.matching_node, context)
            if context.has_errors():
                self.logger.warning("Matching failed, stopping workflow")
                return context
            
            # Conditional: Only proceed if we have matches
            if not context.matched_results:
                self.logger.info("No matches found, skipping research and fabrication")
                return context
            
            # Step 4: Research - Research companies for matched jobs
            context = await self._execute_node(self.research_node, context)
            if context.has_errors():
                self.logger.warning("Research failed, stopping workflow")
                return context
            
            # Step 5: Fabrication - Generate application materials
            context = await self._execute_node(self.fabrication_node, context)
            if context.has_errors():
                self.logger.warning("Fabrication failed, stopping workflow")
                return context
            
            # Step 6: Completion - Check if materials are complete
            context = await self._execute_node(self.completion_node, context)
            if context.has_errors():
                self.logger.warning("Completion check failed, stopping workflow")
                return context
            
            # Step 7: Delivery - Send application materials
            context = await self._execute_node(self.delivery_node, context)
            
        finally:
            # Update execution record as completed
            if execution_id:
                final_status = "failed" if context.has_errors() else "completed"
                self._update_workflow_execution(
                    context,
                    status=final_status,
                )
        
        self.logger.info("Job search workflow completed")
        self.logger.info(f"Execution path: {' -> '.join(self.get_execution_path())}")
        return context
