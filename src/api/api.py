"""FastAPI endpoints for job search workflow."""

import sys
from pathlib import Path

# Add project root to Python path if running directly
# This allows the script to work both as a module and when run directly
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from http import HTTPStatus
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.workflow.job_search_workflow import JobSearchWorkflow
from src.workflow.profiling_workflow import ProfilingWorkflow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Job Agent API", version="1.0.0")


@app.post("/workflow/job-search")
async def run_job_search_workflow(context: JobSearchWorkflow.Context):
    """Run the job search workflow.

    Args:
        context: Job search workflow context with input parameters

    Returns:
        Updated context with results
    """
    logger.info("Received job search workflow request")

    try:
        workflow = JobSearchWorkflow()
        result = await workflow.run(context)

        # Return context as JSON
        # Use mode="json" to ensure UUIDs, datetimes, and Paths are JSON-serializable
        return JSONResponse(
            status_code=HTTPStatus.ACCEPTED,
            content=result.model_dump(mode="json"),
        )
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failed: {str(e)}",
        )


@app.get("/")
async def read_root():
    """Root endpoint."""
    return {"message": "Job Agent API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/workflow/profiling")
async def run_profiling_workflow(context: ProfilingWorkflow.Context):
    """Run the profiling workflow.

    Args:
        context: Profiling workflow context with name, email, cv_urls (list of CV/PDF URLs),
            and optional basic_info. The backend downloads and parses PDFs from the URLs.

    Returns:
        Updated context with profile information and profile_id
    """
    logger.info("Received profiling workflow request")

    try:
        workflow = ProfilingWorkflow()
        result = await workflow.run(context)

        # Return context as JSON
        # Use mode="json" to ensure UUIDs, datetimes, and Paths are JSON-serializable
        return JSONResponse(
            status_code=HTTPStatus.ACCEPTED,
            content=result.model_dump(mode="json"),
        )
    except Exception as e:
        logger.error(f"Profiling workflow execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Profiling workflow execution failed: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
