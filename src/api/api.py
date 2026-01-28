"""FastAPI endpoints for job search workflow."""

from http import HTTPStatus
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.workflow.job_search_workflow import JobSearchWorkflow

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
        return JSONResponse(
            status_code=HTTPStatus.ACCEPTED,
            content=result.model_dump(),
        )
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failed: {str(e)}"
        )


@app.get("/")
async def read_root():
    """Root endpoint."""
    return {"message": "Job Agent API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
