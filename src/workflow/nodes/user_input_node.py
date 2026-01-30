"""User input node for collecting and validating user information."""

from src.workflow.base_node import BaseNode
from src.workflow.profiling_context import ProfilingWorkflowContext


class UserInputNode(BaseNode):
    """Node for collecting and validating user input.

    This node validates that required user information (name, email) is present
    and optionally collects basic information about the user.
    """

    def _validate_context(self, context: ProfilingWorkflowContext) -> bool:
        """Validate required context fields for user input.

        Args:
            context: The workflow context

        Returns:
            True if valid, False otherwise
        """
        if not context.name or not context.name.strip():
            context.add_error("Name is required")
            return False
        if not context.email or not context.email.strip():
            context.add_error("Email is required")
            return False
        return True

    async def _execute(
        self, context: ProfilingWorkflowContext
    ) -> ProfilingWorkflowContext:
        """Validate user input.

        Args:
            context: The workflow context with user input

        Returns:
            Updated context with validated input
        """
        self.logger.info("Validating user input")

        # Validate context
        if not self._validate_context(context):
            self.logger.error("User input validation failed")
            return context

        self.logger.info(f"User input validated: {context.name} ({context.email})")
        return context
