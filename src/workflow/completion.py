"""
Completion detection and delivery preparation for workflow runs.

This module provides functions to check if a run is complete and retrieve
completed items ready for delivery.
"""

import uuid
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from src.database.models import Run, MatchedJob, JobPosting, CompanyResearch, CoverLetter, Artifact


def check_run_completion(session: Session, run_id: str) -> bool:
    """
    Check if all matched jobs in a run have finished (completed or failed).
    
    Args:
        session: SQLAlchemy database session
        run_id: UUID of the run (as string)
    
    Returns:
        True if run is complete, False otherwise
    """
    run = session.query(Run).filter_by(id=uuid.UUID(run_id)).first()
    
    if not run:
        return False
    
    # Get all matched jobs for this run
    matched_jobs = session.query(MatchedJob).filter_by(run_id=uuid.UUID(run_id)).all()
    
    if not matched_jobs:
        # No matched jobs means run is not complete yet (or invalid)
        return False
    
    # Check if all matched jobs have finished research (completed or failed)
    all_research_finished = all(
        matched_job.research_status in ['completed', 'failed']
        for matched_job in matched_jobs
    )
    
    # Check if all matched jobs have finished fabrication (completed or failed)
    all_fabrication_finished = all(
        matched_job.fabrication_status in ['completed', 'failed']
        for matched_job in matched_jobs
    )
    
    # Run is complete if all jobs have finished both research and fabrication
    is_complete = all_research_finished and all_fabrication_finished
    
    if is_complete and run.status != "completed":
        # Update run status
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        session.commit()
    
    return is_complete


def get_completed_items_for_delivery(session: Session, run_id: str) -> List[Dict]:
    """
    Get all successfully completed items (research + fabrication) for delivery.
    
    Args:
        session: SQLAlchemy database session
        run_id: UUID of the run (as string)
    
    Returns:
        List of dictionaries containing job details, research, and cover letter
        Only includes items where both research and fabrication are completed
    """
    # Get matched jobs with both research and fabrication completed
    matched_jobs = session.query(MatchedJob).filter_by(
        run_id=uuid.UUID(run_id),
        research_status="completed",
        fabrication_status="completed"
    ).all()
    
    completed_items = []
    
    for matched_job in matched_jobs:
        # Get job posting
        job_posting = session.query(JobPosting).filter_by(
            id=matched_job.job_posting_id
        ).first()
        
        if not job_posting:
            continue
        
        # Get company research
        company_research = session.query(CompanyResearch).filter_by(
            job_posting_id=matched_job.job_posting_id
        ).first()
        
        # Get artifact (contains both cover letter and CV)
        artifact = session.query(Artifact).filter_by(
            matched_job_id=matched_job.id
        ).first()
        
        if not artifact or not artifact.cover_letter:
            continue
        
        # Extract cover letter and CV from artifact
        cover_letter_data = artifact.cover_letter
        cv_pdf_url = artifact.cv.get("pdf_url") if artifact.cv else None
        
        completed_items.append({
            "matched_job_id": str(matched_job.id),
            "job_posting_id": str(job_posting.id),
            "job_title": job_posting.title,
            "company_name": job_posting.company_name,
            "location": job_posting.location,
            "job_description": job_posting.description,
            "application_link": matched_job.application_link,
            "research": {
                "id": str(company_research.id) if company_research else None,
                "results": company_research.research_results if company_research else None,
                "citations": company_research.citations if company_research else None,
            },
            "cover_letter": {
                "id": str(artifact.id),
                "topic": cover_letter_data.get("topic"),
                "content": cover_letter_data.get("content"),
            },
            "cv": {
                "pdf_url": cv_pdf_url,
            },
        })
    
    return completed_items
