# Langfuse Observability Implementation Guide for Pydantic AI

This guide documents how Langfuse observability is implemented in this repository for monitoring and tracing Pydantic AI agent executions.

## Table of Contents

1. [Overview](#overview)
2. [Setup and Configuration](#setup-and-configuration)
3. [Agent Instrumentation](#agent-instrumentation)
4. [Trace Observation](#trace-observation)
5. [Attribute Propagation](#attribute-propagation)
6. [Implementation Examples](#implementation-examples)
7. [Best Practices](#best-practices)

## Overview

Langfuse provides observability for AI applications by automatically tracing agent executions, capturing inputs/outputs, and creating a hierarchical view of spans. When integrated with Pydantic AI, it enables:

- **Automatic tracing** of agent runs, tool calls, and LLM interactions
- **Visibility** into the full execution flow of AI pipelines
- **Debugging** capabilities with detailed span information
- **Analytics** and monitoring for production environments

## Setup and Configuration

### 1. Environment Variables

Langfuse requires the following environment variables (typically in `.env`):

```bash
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com  # or your self-hosted instance
```

### 2. Configuration Class

The repository uses a configuration class to manage Langfuse settings:

**File**: `consultation/config.py`

```python
@dataclass
class ConsultationConfig:
    # ... other config fields ...
    
    # Langfuse settings
    langfuse_enabled: bool = True
    """Enable Langfuse tracing"""
    
    @classmethod
    def from_env(cls) -> "ConsultationConfig":
        return cls(
            # ... other fields ...
            langfuse_enabled=os.getenv("CONSULTATION_LANGFUSE_ENABLED", "true").lower() == "true",
        )
```

This allows enabling/disabling Langfuse via environment variables.

### 3. Initialization

**File**: `consultation/agents.py`

```python
from langfuse import get_client

def initialize_langfuse() -> None:
    """Initialize and verify Langfuse client."""
    langfuse = get_client()
    if langfuse.auth_check():
        logger.info("Langfuse client is authenticated and ready!")
    else:
        logger.warning("Langfuse authentication failed. Please check your credentials.")
```

**Usage** in main entry point (`consultation/consultation.py`):

```python
# Initialize Langfuse if enabled
if consultation_config.langfuse_enabled:
    initialize_langfuse()
```

## Agent Instrumentation

### 1. Global Instrumentation

**File**: `consultation/consultation.py`

```python
from pydantic_ai import Agent

# Initialize Pydantic AI instrumentation
Agent.instrument_all()
```

This enables automatic instrumentation for all Pydantic AI agents in the application.

### 2. Per-Agent Instrumentation

When creating agents, you can enable/disable instrumentation per agent:

**File**: `consultation/agents.py`

```python
def create_consultation_agent(
    config: ConsultationConfig, deps_type: type = RetrievalDependencies
) -> Agent:
    """Create consultation agent with structured output and instrumentation."""
    return Agent(
        config.consultation_model,
        deps_type=deps_type,
        system_prompt=CONSULTATION_SYSTEM_PROMPT,
        output_type=ConsultationOutput,
        instrument=config.langfuse_enabled,  # Enable/disable per agent
    )


def create_summary_agent(config: ConsultationConfig) -> Agent:
    """Create summary agent for final explanation."""
    return Agent(
        config.summary_model,
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        instrument=config.langfuse_enabled,  # Enable/disable per agent
    )
```

**Key Points**:
- `instrument=True` enables Langfuse tracing for that specific agent
- `instrument=False` disables tracing (useful for testing or specific agents)
- The `instrument` parameter can be controlled via configuration

## Trace Observation

### 1. Using the `@observe()` Decorator

The `@observe()` decorator creates a trace for the entire function execution:

**File**: `consultation/service.py`

```python
from langfuse import observe, propagate_attributes

class ConsultationService:
    @observe()
    async def run_consultation(
        self,
        initial_query: str,
        display_diagnoses_callback,
        get_user_answer_callback,
    ) -> str:
        """Run the iterative consultation loop."""
        # All agent runs within this method will be traced
        # ...
```

**What it does**:
- Creates a top-level trace for the function
- Automatically captures all agent runs, tool calls, and LLM interactions within the function
- Creates a hierarchical span structure

### 2. Manual Trace Updates

You can manually update trace metadata:

**File**: `consultation/service.py`

```python
async def _generate_summary(...) -> str:
    """Generate final summary explanation."""
    # ... generate summary ...
    
    # Update trace output
    if self.config.langfuse_enabled:
        langfuse = get_client()
        langfuse.update_current_trace(output=summary)
    
    return summary
```

**Use Cases**:
- Adding custom output to the trace
- Updating trace metadata after completion
- Adding additional context to the trace

## Attribute Propagation

### 1. Using `propagate_attributes`

The `propagate_attributes` context manager adds metadata to all spans created within its scope:

**File**: `consultation/service.py`

```python
from langfuse import propagate_attributes

@observe()
async def run_consultation(...) -> str:
    # Add attributes to all spans created within this execution scope
    with propagate_attributes(tags=["tcm", "consultation", "diagnosis"]):
        # All agent runs here will have these tags
        conversation_history = []
        # ...
```

### 2. Available Attributes

You can propagate various attributes:

```python
with propagate_attributes(
    user_id="user_123",
    session_id="session_abc",
    tags=["agent", "my-trace"],
    metadata={"email": "user@langfuse.com", "version": "1.0.0"},
    version="1.0.0",
):
    # Your code here
    pass
```

**Attributes**:
- `user_id`: Identify the user
- `session_id`: Group related traces
- `tags`: Categorize traces (list of strings)
- `metadata`: Additional key-value pairs
- `version`: Application version

## Implementation Examples

### Example 1: Simple Agent with Observability

**File**: `playground/langfuse_wrapper.py`

```python
from langfuse import get_client, observe, propagate_attributes
from pydantic_ai import Agent

# Initialize Langfuse
langfuse = get_client()

# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")

# Initialize Pydantic AI instrumentation
Agent.instrument_all()

# Create agent with instrumentation enabled
roulette_agent = Agent(
    "google-gla:gemini-2.5-flash",
    deps_type=int,
    system_prompt="...",
    instrument=True,  # Enable Langfuse tracing
)

# Wrap agent execution with @observe() decorator
@observe()
def roulette_agent_pipeline(input, deps: int):
    # Add attributes to all spans
    with propagate_attributes(
        tags=["agent", "my-trace"],
    ):
        # Run agent - automatically traced
        result = roulette_agent.run_sync(input, deps=deps)
        
        # Update trace with custom output
        langfuse.update_current_trace(
            input=input,
            output=result,
        )
        return result
```

### Example 2: Complex Service with Multiple Agents

**File**: `consultation/service.py`

```python
class ConsultationService:
    def __init__(self, config, retriever, consultation_agent, summary_agent):
        self.config = config
        self.consultation_agent = consultation_agent  # Instrumented
        self.summary_agent = summary_agent  # Instrumented
    
    @observe()
    async def run_consultation(self, initial_query: str, ...) -> str:
        """Main consultation loop - creates top-level trace."""
        with propagate_attributes(tags=["tcm", "consultation", "diagnosis"]):
            while True:
                # Agent run - automatically traced as a span
                result = await self.consultation_agent.run(prompt, deps=deps)
                # ...
            
            # Final summary generation - also traced
            summary = await self._generate_summary(...)
            return summary
    
    async def _generate_summary(...) -> str:
        """Generate summary - creates nested span."""
        # This creates a nested span under the parent trace
        summary_result = await self.summary_agent.run(summary_prompt)
        
        # Update trace output
        if self.config.langfuse_enabled:
            langfuse = get_client()
            langfuse.update_current_trace(output=summary_result.output)
        
        return summary_result.output
```

## Best Practices

### 1. Conditional Instrumentation

Always check configuration before enabling instrumentation:

```python
# Good: Configurable
agent = Agent(
    model="...",
    instrument=config.langfuse_enabled,
)

# Avoid: Hardcoded
agent = Agent(
    model="...",
    instrument=True,  # Always enabled
)
```

### 2. Initialize Once

Initialize Langfuse once at application startup:

```python
# In main entry point
if config.langfuse_enabled:
    initialize_langfuse()
    Agent.instrument_all()
```

### 3. Use Meaningful Tags

Use tags to categorize traces for filtering and analysis:

```python
with propagate_attributes(
    tags=["tcm", "consultation", "diagnosis"],  # Clear, hierarchical tags
):
    # ...
```

### 4. Update Trace Output

Manually update trace output for important results:

```python
# After generating final result
if config.langfuse_enabled:
    langfuse = get_client()
    langfuse.update_current_trace(output=final_result)
```

### 5. Error Handling

Don't let Langfuse errors break your application:

```python
def initialize_langfuse() -> None:
    try:
        langfuse = get_client()
        if langfuse.auth_check():
            logger.info("Langfuse ready!")
        else:
            logger.warning("Langfuse auth failed - continuing without tracing")
    except Exception as e:
        logger.warning(f"Langfuse initialization failed: {e} - continuing without tracing")
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

Structure traces hierarchically for better visualization:

```
Trace: run_consultation()
  ├─ Span: consultation_agent.run() (iteration 1)
  │   ├─ Span: LLM call
  │   └─ Span: Tool call (if any)
  ├─ Span: consultation_agent.run() (iteration 2)
  │   └─ ...
  └─ Span: _generate_summary()
      └─ Span: summary_agent.run()
```

## File Structure

The Langfuse implementation is organized across these files:

```
consultation/
├── config.py              # Configuration with langfuse_enabled flag
├── agents.py              # Agent creation with instrument parameter
│                         # + initialize_langfuse() function
├── service.py             # @observe() decorator and propagate_attributes
└── consultation.py       # Agent.instrument_all() initialization

playground/
└── langfuse_wrapper.py   # Example implementation
```

## Summary

The Langfuse observability implementation in this repository follows these patterns:

1. **Configuration-driven**: Langfuse can be enabled/disabled via config
2. **Global instrumentation**: `Agent.instrument_all()` enables tracing for all agents
3. **Per-agent control**: `instrument=True/False` parameter for fine-grained control
4. **Trace observation**: `@observe()` decorator for top-level traces
5. **Attribute propagation**: `propagate_attributes()` for adding metadata
6. **Manual updates**: `update_current_trace()` for custom output

This setup provides comprehensive observability while maintaining flexibility and performance.
