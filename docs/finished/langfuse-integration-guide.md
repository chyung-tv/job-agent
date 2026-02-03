# Langfuse Integration Guide for Job Agent Project

This guide provides step-by-step instructions for integrating Langfuse observability into the job agent project to track and monitor agent steps within Celery workflows.

## Table of Contents

1. [Overview](#overview)
2. [Setup and Configuration](#setup-and-configuration)
3. [Integration Points](#integration-points)
4. [Agent Instrumentation](#agent-instrumentation)
5. [Workflow and Node Tracking](#workflow-and-node-tracking)
6. [Celery Task Integration](#celery-task-integration)
7. [Implementation Examples](#implementation-examples)
8. [Best Practices](#best-practices)

## Overview

Langfuse will provide observability for:
- **Celery Task Execution**: Track when workflows are enqueued and executed
- **Workflow Execution**: Monitor entire workflow runs (profiling, job search)
- **Node Execution**: Track each node step (MatchingNode, ResearchNode, etc.)
- **Agent Calls**: Detailed tracing of Pydantic AI agent interactions
- **LLM Interactions**: Automatic capture of LLM calls, tokens, latency
- **Error Tracking**: Capture failures at any level with full context

### Trace Hierarchy

```
Trace: Celery Task (profiling_workflow / job_search_workflow)
  ├─ Span: Workflow.run()
  │   ├─ Span: Node 1 (e.g., UserInputNode)
  │   │   └─ Span: Agent.run() (if agent used)
  │   │       └─ Span: LLM Call
  │   ├─ Span: Node 2 (e.g., CVProcessingNode)
  │   │   └─ Span: Agent.run()
  │   │       └─ Span: LLM Call
  │   └─ Span: Node N (e.g., MatchingNode)
  │       └─ Span: Agent.run() (per job)
  │           └─ Span: LLM Call
```

## Setup and Configuration

### 1. Install Dependencies

Add Langfuse to your dependencies:

**File**: `pyproject.toml`

```toml
dependencies = [
    # ... existing dependencies ...
    "langfuse>=2.0.0",
]
```

### 2. Environment Variables

Add Langfuse configuration to `.env`:

```bash
# Langfuse Configuration
LANGFUSE_PUBLIC_KEY=your_public_key_here
LANGFUSE_SECRET_KEY=your_secret_key_here
LANGFUSE_HOST=https://cloud.langfuse.com  # or your self-hosted instance

# Optional: Enable/disable Langfuse
LANGFUSE_ENABLED=true
```

### 3. Create Configuration Module

**File**: `src/config.py` (or add to existing config)

```python
"""Configuration management."""
import os
from dataclasses import dataclass

@dataclass
class LangfuseConfig:
    """Langfuse configuration."""
    enabled: bool = True
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"
    
    @classmethod
    def from_env(cls) -> "LangfuseConfig":
        """Load configuration from environment variables."""
        return cls(
            enabled=os.getenv("LANGFUSE_ENABLED", "true").lower() == "true",
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
```

## Integration Points

### 1. Initialize Langfuse in Celery App

Langfuse must be initialized before any agents are created. Initialize it in the Celery app:

**File**: `src/celery_app.py`

```python
"""Celery application configuration."""
import os
from celery import Celery
from celery.schedules import crontab

# Initialize Langfuse BEFORE creating agents
from langfuse import Langfuse
from src.config import LangfuseConfig

langfuse_config = LangfuseConfig.from_env()

if langfuse_config.enabled and langfuse_config.public_key and langfuse_config.secret_key:
    try:
        langfuse_client = Langfuse(
            public_key=langfuse_config.public_key,
            secret_key=langfuse_config.secret_key,
            host=langfuse_config.host,
        )
        # Verify connection
        if langfuse_client.auth_check():
            print("✓ Langfuse initialized successfully")
        else:
            print("⚠ Langfuse authentication failed - continuing without tracing")
            langfuse_client = None
    except Exception as e:
        print(f"⚠ Langfuse initialization failed: {e} - continuing without tracing")
        langfuse_client = None
else:
    langfuse_client = None

# Initialize Pydantic AI instrumentation if Langfuse is enabled
if langfuse_client:
    from pydantic_ai import Agent
    Agent.instrument_all()
    print("✓ Pydantic AI instrumentation enabled")

# Get Redis URL from environment
redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "job_agent",
    broker=redis_url,
    backend=redis_url,
    include=[
        "src.tasks.profiling_task",
        "src.tasks.job_search_task",
        "src.tasks.scheduled_tasks",
    ],
)

# ... rest of Celery configuration ...
```

### 2. Create Langfuse Utilities Module

**File**: `src/langfuse_utils.py`

```python
"""Langfuse utility functions for workflow tracking."""
import logging
from typing import Optional, Dict, Any
from langfuse import Langfuse, get_client, observe, propagate_attributes
from src.config import LangfuseConfig

logger = logging.getLogger(__name__)
langfuse_config = LangfuseConfig.from_env()

def get_langfuse_client() -> Optional[Langfuse]:
    """Get Langfuse client if enabled.
    
    Returns:
        Langfuse client instance or None if disabled
    """
    if not langfuse_config.enabled:
        return None
    
    try:
        return get_client()
    except Exception as e:
        logger.warning(f"Failed to get Langfuse client: {e}")
        return None


def create_workflow_trace_context(
    execution_id: Optional[str] = None,
    run_id: Optional[str] = None,
    workflow_type: Optional[str] = None,
    node_name: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create context attributes for Langfuse trace propagation.
    
    Args:
        execution_id: WorkflowExecution ID
        run_id: Run ID
        workflow_type: Type of workflow (profiling, job_search)
        node_name: Current node name
        user_id: User identifier (if available)
        metadata: Additional metadata
        
    Returns:
        Dictionary of attributes for propagate_attributes
    """
    tags = []
    if workflow_type:
        tags.append(workflow_type)
    if node_name:
        tags.append(node_name)
    
    attrs = {
        "tags": tags,
        "metadata": metadata or {},
    }
    
    if execution_id:
        attrs["metadata"]["execution_id"] = execution_id
    if run_id:
        attrs["metadata"]["run_id"] = run_id
    if workflow_type:
        attrs["metadata"]["workflow_type"] = workflow_type
    if node_name:
        attrs["metadata"]["node_name"] = node_name
    if user_id:
        attrs["user_id"] = user_id
    
    return attrs


# Re-export commonly used decorators and context managers
__all__ = [
    "get_langfuse_client",
    "create_workflow_trace_context",
    "observe",
    "propagate_attributes",
]
```

## Agent Instrumentation

### 1. Update Node Classes to Instrument Agents

Agents should be created with `instrument=True` when Langfuse is enabled. Update each node that creates agents:

**File**: `src/workflow/nodes/matching_node.py`

```python
"""Matching node for screening jobs against user profiles."""
import uuid
import hashlib
from typing import List, Optional
import logging

from pydantic_ai import Agent
from pydantic import BaseModel, Field
from src.discovery.serpapi_models import JobResult
from src.workflow.base_node import BaseNode
from src.workflow.base_context import JobSearchWorkflowContext
from src.matcher.matcher import JobScreeningOutput as MatcherJobScreeningOutput
from src.database import db_session, GenericRepository, MatchedJob, JobPosting, JobSearch
from src.langfuse_utils import get_langfuse_client, create_workflow_trace_context, propagate_attributes
from src.config import LangfuseConfig
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
langfuse_config = LangfuseConfig.from_env()

# Use JobScreeningOutput from matcher module to maintain compatibility
JobScreeningOutput = MatcherJobScreeningOutput


class MatchingNode(BaseNode):
    """Node for matching jobs against user profiles using AI."""
    
    def __init__(self, model: str = "google-gla:gemini-2.5-flash"):
        """Initialize the matching node.
        
        Args:
            model: The AI model to use for job matching
        """
        super().__init__()
        # Enable Langfuse instrumentation for agent
        self.agent = Agent(
            model=model,
            output_type=JobScreeningOutput,
            instrument=langfuse_config.enabled,  # Enable tracing if Langfuse is enabled
        )
    
    # ... existing methods ...
    
    async def _match_job(
        self,
        user_profile: str,
        job: JobResult,
        context: JobSearchWorkflowContext,  # Add context parameter
    ) -> Optional[JobScreeningOutput]:
        """Match a single job against a user profile.
        
        Args:
            user_profile: The user's profile/skills description
            job: The job posting to match
            context: The workflow context for trace propagation
            
        Returns:
            JobScreeningOutput if successful, None if job is invalid or matching fails
        """
        if not job.title or not job.job_id:
            return None
        
        try:
            # Create trace context for this job matching operation
            trace_context = create_workflow_trace_context(
                execution_id=str(context.run_id) if context.run_id else None,
                run_id=str(context.run_id) if context.run_id else None,
                workflow_type="job_search",
                node_name="MatchingNode",
                metadata={
                    "job_id": job.job_id,
                    "job_title": job.title,
                    "company_name": job.company_name,
                },
            )
            
            # Propagate attributes to all spans created within this scope
            with propagate_attributes(**trace_context):
                prompt = self._build_prompt(user_profile, job)
                # Agent.run() will automatically create a span with Langfuse
                result = await self.agent.run(prompt)
                output = result.output
                
                # Ensure job_id is set from original job if AI didn't return it correctly
                if not output.job_id or output.job_id.strip() == "":
                    output.job_id = job.job_id
                # Ensure reason is always present
                if not output.reason or output.reason.strip() == "":
                    output.reason = "AI agent did not provide a reason for this match decision."
                
                return output
        except Exception as e:
            self.logger.warning(f"Failed to match job {job.job_id}: {e}")
            return None
    
    async def run(self, context: JobSearchWorkflowContext) -> JobSearchWorkflowContext:
        """Screen jobs against user profile.
        
        Args:
            context: The workflow context with user_profile and jobs
            
        Returns:
            Updated context with matching results
        """
        self.logger.info("Starting matching node")
        
        # Validate context
        if not self._validate_context(context):
            self.logger.error("Context validation failed")
            return context
        
        # Load jobs from database if needed
        session_gen = self._get_db_session()
        session = next(session_gen)
        try:
            self._load_data(context, session)
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass
        
        if not context.jobs:
            context.add_error("No jobs available for matching")
            self.logger.error("No jobs available for matching")
            return context
        
        # Screen jobs
        jobs_to_screen = context.jobs[:context.max_screening] if context.max_screening else context.jobs
        matched_results: List[JobScreeningOutput] = []
        all_screening_results: List[JobScreeningOutput] = []
        
        self.logger.info(f"Matching {len(jobs_to_screen)} jobs against user profile...")
        
        # Update _match_job calls to pass context
        for job in jobs_to_screen:
            result = await self._match_job(context.user_profile, job, context)  # Pass context
            if not result:
                continue
            
            all_screening_results.append(result)
            
            status = "MATCH" if result.is_match else "No match"
            self.logger.info(f"{status} - {result.job_title} at {result.job_company}")
            
            if result.is_match:
                matched_results.append(result)
        
        # Update context
        context.matched_results = matched_results
        context.all_screening_results = all_screening_results
        
        # Persist to database
        if context.job_search_id:
            session_gen = self._get_db_session()
            session = next(session_gen)
            try:
                self._persist_data(context, session)
            except Exception as e:
                self.logger.error(f"Failed to persist matched jobs: {e}")
                context.add_error(f"Failed to save matched jobs to database: {e}")
            finally:
                try:
                    next(session_gen, None)
                except StopIteration:
                    pass
        
        self.logger.info(f"Matching node completed: {len(matched_results)} matches found")
        return context
```

### 2. Update Other Nodes Similarly

Apply the same pattern to other nodes that use agents:

- **CVProcessingNode** (`src/workflow/nodes/cv_processing_node.py`)
- **ResearchNode** (if it uses agents)
- **FabricationNode** (if it uses agents)
- Any other nodes with agents

## Workflow and Node Tracking

### 1. Wrap Workflow Execution with @observe()

**File**: `src/workflow/base_workflow.py`

```python
"""Base workflow class for flexible workflow orchestration."""
import uuid
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy.orm import Session
from langfuse import observe, propagate_attributes

from src.database import db_session, Run, WorkflowExecution
from src.langfuse_utils import create_workflow_trace_context

if TYPE_CHECKING:
    from src.workflow.base_context import BaseContext
    from src.workflow.base_node import BaseNode

logger = logging.getLogger(__name__)


class BaseWorkflow(ABC):
    """Base class for all workflows providing common functionality."""
    
    def __init__(self, workflow_type: str = "generic"):
        """Initialize the base workflow."""
        self.workflow_type = workflow_type
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.execution_history: List[ExecutionRecord] = []
        self._execution_id: Optional[uuid.UUID] = None
    
    # ... existing methods ...
    
    @observe()  # Add @observe() decorator to track workflow execution
    async def run(self, context: "BaseContext") -> "BaseContext":
        """Execute the workflow with flexible node execution.
        
        This method is automatically traced by Langfuse.
        
        Args:
            context: The workflow context with input parameters
            
        Returns:
            Updated context with results
        """
        # Create trace context for this workflow execution
        trace_context = create_workflow_trace_context(
            execution_id=str(self._execution_id) if self._execution_id else None,
            run_id=str(context.run_id) if context.run_id else None,
            workflow_type=self.workflow_type,
            metadata={
                "workflow_class": self.__class__.__name__,
            },
        )
        
        # Propagate attributes to all spans created within this workflow
        with propagate_attributes(**trace_context):
            self.logger.info(f"Starting {self.workflow_type} workflow")
            
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
            
            # Execute workflow-specific logic (implemented in subclasses)
            try:
                result = await self._execute(context)
                
                # Update execution status
                if execution_id:
                    final_status = "failed" if result.has_errors() else "completed"
                    self._update_workflow_execution(
                        context=result,
                        status=final_status,
                        error_message="; ".join(result.errors) if result.has_errors() else None,
                    )
                
                return result
            except Exception as e:
                self.logger.error(f"Workflow execution failed: {e}", exc_info=True)
                if execution_id:
                    self._update_workflow_execution(
                        context=context,
                        status="failed",
                        error_message=str(e),
                    )
                raise
    
    @abstractmethod
    async def _execute(self, context: "BaseContext") -> "BaseContext":
        """Execute workflow-specific logic.
        
        This method should be implemented by subclasses.
        """
        pass
    
    # ... rest of existing methods ...
```

### 2. Wrap Node Execution

**File**: `src/workflow/base_node.py`

```python
"""Base class for all workflow nodes."""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
import logging
from langfuse import observe, propagate_attributes
from src.langfuse_utils import create_workflow_trace_context

if TYPE_CHECKING:
    from src.workflow.base_context import BaseContext

logger = logging.getLogger(__name__)


class BaseNode(ABC):
    """Base class for all workflow nodes."""
    
    def __init__(self):
        """Initialize the node."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @observe()  # Add @observe() decorator to track node execution
    async def run(self, context: "BaseContext") -> "BaseContext":
        """Process context and return updated context.
        
        This method is automatically traced by Langfuse.
        
        Args:
            context: The workflow context to process
            
        Returns:
            Updated context with results
        """
        node_name = self.__class__.__name__
        
        # Create trace context for this node execution
        trace_context = create_workflow_trace_context(
            execution_id=str(context.run_id) if hasattr(context, 'run_id') and context.run_id else None,
            run_id=str(context.run_id) if hasattr(context, 'run_id') and context.run_id else None,
            workflow_type=getattr(context, 'workflow_type', None),
            node_name=node_name,
            metadata={
                "node_class": node_name,
            },
        )
        
        # Propagate attributes to all spans created within this node
        with propagate_attributes(**trace_context):
            self.logger.info(f"Starting {node_name}")
            
            # Validate context
            if hasattr(self, '_validate_context'):
                if not self._validate_context(context):
                    self.logger.error(f"{node_name} validation failed")
                    return context
            
            # Load data
            session_gen = self._get_db_session()
            session = next(session_gen)
            try:
                if hasattr(self, '_load_data'):
                    self._load_data(context, session)
            finally:
                try:
                    next(session_gen, None)
                except StopIteration:
                    pass
            
            # Execute node-specific logic (implemented in subclasses)
            try:
                result = await self._execute(context)
                
                # Persist data
                session_gen = self._get_db_session()
                session = next(session_gen)
                try:
                    if hasattr(self, '_persist_data'):
                        self._persist_data(result, session)
                finally:
                    try:
                        next(session_gen, None)
                    except StopIteration:
                        pass
                
                self.logger.info(f"{node_name} completed successfully")
                return result
            except Exception as e:
                self.logger.error(f"{node_name} execution failed: {e}", exc_info=True)
                if hasattr(context, 'add_error'):
                    context.add_error(f"{node_name} failed: {e}")
                return context
    
    @abstractmethod
    async def _execute(self, context: "BaseContext") -> "BaseContext":
        """Execute node-specific logic.
        
        This method should be implemented by subclasses.
        """
        pass
    
    # ... rest of existing methods ...
```

**Note**: This approach wraps the base `run()` method. If your nodes override `run()` directly, you'll need to add `@observe()` to each node's `run()` method instead.

## Celery Task Integration

### 1. Wrap Celery Tasks with @observe()

**File**: `src/tasks/profiling_task.py`

```python
"""Celery task for profiling workflow."""
import asyncio
import logging
from typing import Dict, Any

from src.celery_app import celery_app
from src.workflow.profiling_workflow import ProfilingWorkflow
from src.workflow.profiling_context import ProfilingWorkflowContext
from src.tasks.utils import update_execution_status
from langfuse import observe, propagate_attributes
from src.langfuse_utils import create_workflow_trace_context, get_langfuse_client
from src.config import LangfuseConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)

logger = logging.getLogger(__name__)
langfuse_config = LangfuseConfig.from_env()


def run_async(coro):
    """Helper to run async function in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.run(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(bind=True, name="profiling_workflow")
@observe()  # Add @observe() decorator to track Celery task execution
def execute_profiling_workflow(
    self,
    context_data: Dict[str, Any],
    execution_id: str = None,
) -> Dict[str, Any]:
    """Execute profiling workflow as Celery task.
    
    This task is automatically traced by Langfuse.
    
    Args:
        context_data: Serialized ProfilingWorkflowContext data
        execution_id: UUID string of the workflow execution record
        
    Returns:
        Serialized context with results
    """
    logger.info(
        f"Starting profiling workflow task (execution_id: {execution_id}, task_id: {self.request.id})"
    )
    
    # Create trace context for this Celery task
    trace_context = create_workflow_trace_context(
        execution_id=execution_id,
        workflow_type="profiling",
        metadata={
            "celery_task_id": self.request.id,
            "celery_task_name": "profiling_workflow",
        },
    )
    
    # Propagate attributes to all spans created within this task
    with propagate_attributes(**trace_context):
        try:
            # Update status to processing
            if execution_id:
                update_execution_status(
                    execution_id, "processing", current_node="ProfilingWorkflow"
                )
            
            # Reconstruct context from dict
            context = ProfilingWorkflowContext(**context_data)
            logger.info(f"Reconstructed context for {context.name} ({context.email})")
            
            # Execute workflow (async)
            logger.info("Executing profiling workflow...")
            workflow = ProfilingWorkflow()
            result = run_async(workflow.run(context))
            logger.info(f"Workflow execution completed. Has errors: {result.has_errors()}")
            
            # Update status to completed
            if execution_id:
                final_status = "failed" if result.has_errors() else "completed"
                error_message = "; ".join(result.errors) if result.has_errors() else None
                update_execution_status(
                    execution_id,
                    final_status,
                    error_message=error_message,
                    context_snapshot=result.model_dump(mode="json"),
                )
                logger.info(f"Updated execution status to: {final_status}")
            
            profile_id = result.profile_id if hasattr(result, "profile_id") else "N/A"
            logger.info(
                f"Profiling workflow task completed successfully (execution_id: {execution_id}, profile_id: {profile_id})"
            )
            
            # Update trace output with final result
            if langfuse_config.enabled:
                langfuse = get_langfuse_client()
                if langfuse:
                    try:
                        langfuse.update_current_trace(
                            output={
                                "status": final_status if execution_id else "completed",
                                "profile_id": profile_id,
                                "has_errors": result.has_errors(),
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update Langfuse trace: {e}")
            
            # Return serialized result
            return result.model_dump(mode="json")
            
        except Exception as exc:
            logger.error(f"Profiling workflow failed: {exc}", exc_info=True)
            
            # Update status to failed
            if execution_id:
                try:
                    update_execution_status(
                        execution_id,
                        "failed",
                        error_message=str(exc),
                    )
                except Exception as update_error:
                    logger.error(
                        f"Failed to update execution status: {update_error}", exc_info=True
                    )
            
            # Retry task on failure
            raise self.retry(exc=exc, countdown=60, max_retries=3)
```

### 2. Update Job Search Task Similarly

**File**: `src/tasks/job_search_task.py`

Apply the same pattern:

```python
@celery_app.task(bind=True, name="job_search_workflow")
@observe()  # Add @observe() decorator
def execute_job_search_workflow(
    self,
    context_data: Dict[str, Any],
    execution_id: str = None,
) -> Dict[str, Any]:
    """Execute job search workflow as Celery task."""
    # ... same pattern as profiling_task ...
```

## Implementation Examples

### Example 1: Complete Node with Langfuse

**File**: `src/workflow/nodes/cv_processing_node.py` (excerpt)

```python
from pydantic_ai import Agent
from langfuse import propagate_attributes
from src.langfuse_utils import create_workflow_trace_context
from src.config import LangfuseConfig

langfuse_config = LangfuseConfig.from_env()

class CVProcessingNode(BaseNode):
    def __init__(self, model: str = "google-gla:gemini-2.5-flash"):
        super().__init__()
        self.model = model
    
    async def run(self, context: ProfilingWorkflowContext) -> ProfilingWorkflowContext:
        """Process CV/PDF documents from URLs."""
        # Create trace context
        trace_context = create_workflow_trace_context(
            run_id=str(context.run_id) if context.run_id else None,
            workflow_type="profiling",
            node_name="CVProcessingNode",
            metadata={
                "cv_urls_count": len(context.cv_urls) if context.cv_urls else 0,
            },
        )
        
        with propagate_attributes(**trace_context):
            # Extract text from PDFs
            raw_text = self._build_profile_from_urls(context.cv_urls)
            context.raw_cv_text = raw_text
            
            if not raw_text.strip():
                context.add_error("No PDF content extracted")
                return context
            
            # Create agent with instrumentation
            profiling_agent = Agent(
                model=self.model,
                output_type=ProfilingOutput,
                instrument=langfuse_config.enabled,  # Enable tracing
            )
            
            # Build prompt
            prompt = f"""Extract and structure a comprehensive user profile..."""
            
            # Agent.run() will automatically create a Langfuse span
            result = await profiling_agent.run(prompt)
            context.profile_data = result.output
            
            return context
```

### Example 2: Tracking Multiple Agent Calls in a Loop

**File**: `src/workflow/nodes/matching_node.py` (excerpt)

```python
async def run(self, context: JobSearchWorkflowContext) -> JobSearchWorkflowContext:
    """Screen jobs against user profile."""
    # ... validation and setup ...
    
    # Each job matching will create its own span
    for job in jobs_to_screen:
        # _match_job already has propagate_attributes context
        result = await self._match_job(context.user_profile, job, context)
        if result and result.is_match:
            matched_results.append(result)
    
    context.matched_results = matched_results
    return context
```

## Best Practices

### 1. Conditional Instrumentation

Always check configuration before enabling instrumentation:

```python
# Good: Configurable
agent = Agent(
    model="...",
    instrument=langfuse_config.enabled,
)

# Avoid: Hardcoded
agent = Agent(
    model="...",
    instrument=True,  # Always enabled
)
```

### 2. Initialize Once

Initialize Langfuse once at application startup (in `celery_app.py`):

```python
# In celery_app.py
if langfuse_config.enabled:
    langfuse_client = Langfuse(...)
    Agent.instrument_all()
```

### 3. Use Meaningful Metadata

Add relevant context to traces:

```python
trace_context = create_workflow_trace_context(
    execution_id=execution_id,
    run_id=run_id,
    workflow_type="job_search",
    node_name="MatchingNode",
    metadata={
        "job_id": job.job_id,
        "job_title": job.title,
        "company_name": job.company_name,
        "user_profile_length": len(user_profile),
    },
)
```

### 4. Error Handling

Don't let Langfuse errors break your application:

```python
try:
    langfuse = get_langfuse_client()
    if langfuse:
        langfuse.update_current_trace(output=result)
except Exception as e:
    logger.warning(f"Failed to update Langfuse trace: {e}")
    # Continue execution
```

### 5. Update Trace Output

Manually update trace output for important results:

```python
if langfuse_config.enabled:
    langfuse = get_langfuse_client()
    if langfuse:
        langfuse.update_current_trace(
            output={
                "status": "completed",
                "matches_found": len(matched_results),
                "profile_id": profile_id,
            }
        )
```

### 6. Async Support

Use async/await properly with Langfuse:

```python
@observe()
async def my_async_function():
    with propagate_attributes(tags=["async"]):
        result = await agent.run(...)
        return result
```

### 7. Trace Hierarchy

Structure traces hierarchically:

```
Trace: Celery Task (profiling_workflow)
  └─ Span: ProfilingWorkflow.run()
      ├─ Span: UserInputNode.run()
      ├─ Span: CVProcessingNode.run()
      │   └─ Span: Agent.run()
      │       └─ Span: LLM Call
      └─ Span: CompletionNode.run()
```

## Testing

### 1. Verify Langfuse Initialization

```python
# In celery_app.py or test script
from src.langfuse_utils import get_langfuse_client

langfuse = get_langfuse_client()
if langfuse and langfuse.auth_check():
    print("✓ Langfuse is ready")
else:
    print("⚠ Langfuse is not available")
```

### 2. Test Agent Instrumentation

```python
# Create a test agent
from pydantic_ai import Agent
from src.config import LangfuseConfig

config = LangfuseConfig.from_env()
agent = Agent(
    model="google-gla:gemini-2.5-flash",
    instrument=config.enabled,
)

# Run agent - should create trace in Langfuse
result = await agent.run("Test prompt")
```

### 3. Check Langfuse Dashboard

1. Go to your Langfuse dashboard
2. Navigate to "Traces"
3. Look for traces with tags matching your workflow types
4. Verify spans are created for each node and agent call

## Troubleshooting

### Issue: No traces appearing in Langfuse

**Solutions**:
1. Check environment variables are set correctly
2. Verify `LANGFUSE_ENABLED=true`
3. Check Langfuse client initialization logs
4. Ensure `Agent.instrument_all()` is called before creating agents

### Issue: Traces missing node information

**Solutions**:
1. Ensure `propagate_attributes()` is used in node `run()` methods
2. Check that `create_workflow_trace_context()` includes node_name
3. Verify context is passed to agent calls

### Issue: Too many traces or performance impact

**Solutions**:
1. Disable Langfuse in development: `LANGFUSE_ENABLED=false`
2. Use sampling: Only enable for specific workflows
3. Check Langfuse batch settings

## Summary

This integration provides:

1. **Celery Task Tracking**: Each workflow task execution is traced
2. **Workflow Tracking**: Entire workflow runs are monitored
3. **Node Tracking**: Each node execution creates a span
4. **Agent Tracking**: All Pydantic AI agent calls are automatically traced
5. **LLM Tracking**: LLM interactions, tokens, and latency are captured
6. **Error Tracking**: Failures at any level are captured with full context

The implementation is:
- **Non-intrusive**: Can be disabled via configuration
- **Hierarchical**: Traces follow the natural workflow structure
- **Contextual**: Rich metadata at every level
- **Automatic**: Minimal code changes required

## Next Steps

1. Add Langfuse dependencies to `pyproject.toml`
2. Create `src/config.py` with LangfuseConfig
3. Create `src/langfuse_utils.py` utility module
4. Update `src/celery_app.py` to initialize Langfuse
5. Update node classes to instrument agents
6. Add `@observe()` decorators to workflows and tasks
7. Test with a sample workflow execution
8. Verify traces appear in Langfuse dashboard
