"""Research node for researching companies for matched jobs."""

import os
import uuid
from typing import Optional, Dict
import logging
from datetime import datetime

from exa_py import Exa
from sqlalchemy.orm import Session

from src.workflow.base_node import BaseNode
from src.workflow.base_context import JobSearchWorkflowContext
from src.database import db_session, GenericRepository, MatchedJob, JobPosting, CompanyResearch, Run
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ResearchNode(BaseNode):
    """Node for researching companies for matched jobs using Exa API."""
    
    def __init__(self, use_streaming: bool = False, max_retries: int = 3):
        """Initialize the research node.
        
        Args:
            use_streaming: If True, use streaming mode for Exa API
            max_retries: Maximum number of retry attempts
        """
        super().__init__()
        self.use_streaming = use_streaming
        self.max_retries = max_retries
        self.exa = Exa(api_key=os.getenv("EXA_API_KEY"))
    
    def _validate_context(self, context: JobSearchWorkflowContext) -> bool:
        """Validate required context fields for research.
        
        Args:
            context: The workflow context
            
        Returns:
            True if valid, False otherwise
        """
        if not context.run_id:
            context.add_error("Run ID is required for research step")
            return False
        return True
    
    def _get_research_by_job_posting(self, session: Session, job_posting_id: str) -> Optional[CompanyResearch]:
        """Get existing research for a job posting.
        
        Args:
            session: Database session
            job_posting_id: Job posting ID
            
        Returns:
            CompanyResearch if found, None otherwise
        """
        return session.query(CompanyResearch).filter_by(job_posting_id=uuid.UUID(job_posting_id)).first()
    
    def _save_research_results(
        self,
        session: Session,
        job_posting_id: str,
        company_name: str,
        research_results: str,
        citations: list,
    ) -> CompanyResearch:
        """Save research results to database.
        
        Args:
            session: Database session
            job_posting_id: Job posting ID
            company_name: Company name
            research_results: Research text
            citations: List of citations
            
        Returns:
            Created or updated CompanyResearch
        """
        existing = self._get_research_by_job_posting(session, job_posting_id)
        
        if existing:
            existing.research_results = research_results
            existing.citations = [{"url": getattr(c, 'url', ''), "title": getattr(c, 'title', '')} for c in citations] if citations else []
            session.commit()
            return existing
        else:
            new_research = CompanyResearch(
                id=uuid.uuid4(),
                job_posting_id=uuid.UUID(job_posting_id),
                company_name=company_name,
                research_results=research_results,
                citations=[{"url": getattr(c, 'url', ''), "title": getattr(c, 'title', '')} for c in citations] if citations else [],
            )
            session.add(new_research)
            session.commit()
            return new_research
    
    async def _research_company_for_job(
        self,
        session: Session,
        matched_job: MatchedJob,
        job_posting: JobPosting,
    ) -> Optional[Dict]:
        """Research company information for a job posting.
        
        Args:
            session: Database session
            matched_job: MatchedJob object
            job_posting: JobPosting object
            
        Returns:
            Dict with 'answer' and 'citations' if successful, None otherwise
        """
        # Check if research already exists
        existing_research = self._get_research_by_job_posting(session, str(job_posting.id))
        if existing_research:
            was_completed = matched_job.research_status == "completed"
            matched_job.research_status = "completed"
            matched_job.research_completed_at = datetime.utcnow()
            matched_job.research_error = None
            
            if matched_job.run_id and not was_completed:
                run = session.query(Run).filter_by(id=matched_job.run_id).first()
                if run:
                    run.research_completed_count += 1
                    session.commit()
            
            session.commit()
            self.logger.info("Research already exists, using existing research")
            return {
                "answer": existing_research.research_results,
                "citations": existing_research.citations or []
            }
        
        # Update status to processing
        matched_job.research_status = "processing"
        matched_job.research_attempts += 1
        session.commit()
        
        try:
            query = f"""Research {job_posting.company_name}, a company hiring for the position of {job_posting.title}. 

Please provide comprehensive information about:
1. Company background: What does this company do? What is their mission and history?
2. Team and culture: What is the team structure like? What is the company culture?
3. Candidate expectations: Based on the job posting and company culture, what do they expect from candidates for this role?
4. Current activities: What are they currently working on? Any recent news, product launches, or major initiatives?

Focus on information that would help a candidate prepare for an interview with this company.
"""
            
            self.logger.info(f"Researching: {job_posting.company_name} - {job_posting.title}")
            
            answer_text = ""
            citations = []
            
            # Exa API calls are synchronous, but we're in async function
            # We'll use the stream_answer method
            for chunk in self.exa.stream_answer(query, text=True):
                if hasattr(chunk, 'content') and chunk.content:
                    answer_text += chunk.content
                
                if hasattr(chunk, 'citations') and chunk.citations:
                    citations = chunk.citations
            
            if not answer_text:
                self.logger.warning("No research results received from Exa API")
                raise ValueError("No research results received")
            
            # Save research results
            self._save_research_results(
                session=session,
                job_posting_id=str(job_posting.id),
                company_name=job_posting.company_name,
                research_results=answer_text,
                citations=citations,
            )
            
            # Update matched job status
            was_completed = matched_job.research_status == "completed"
            matched_job.research_status = "completed"
            matched_job.research_completed_at = datetime.utcnow()
            matched_job.research_error = None
            
            if matched_job.run_id and not was_completed:
                run = session.query(Run).filter_by(id=matched_job.run_id).first()
                if run:
                    run.research_completed_count += 1
                    session.commit()
            
            session.commit()
            
            return {
                "answer": answer_text,
                "citations": citations
            }
        
        except Exception as e:
            error_msg = str(e)
            matched_job.research_status = "failed" if matched_job.research_attempts >= self.max_retries else "pending"
            matched_job.research_error = error_msg
            
            if matched_job.run_id and matched_job.research_attempts >= self.max_retries:
                run = session.query(Run).filter_by(id=matched_job.run_id).first()
                if run:
                    run.research_failed_count += 1
                    session.commit()
            
            session.commit()
            self.logger.error(f"Research failed (attempt {matched_job.research_attempts}/{self.max_retries}): {error_msg}")
            return None
    
    def _load_data(self, context: JobSearchWorkflowContext, session: Session) -> None:
        """Load matched jobs for research.
        
        Args:
            context: The workflow context
            session: Database session
        """
        # Matched jobs will be loaded in run() method
        pass
    
    def _persist_data(self, context: JobSearchWorkflowContext, session: Session) -> None:
        """Persist research results (already done in _research_company_for_job).
        
        Args:
            context: The workflow context
            session: Database session
        """
        # Persistence is handled in _research_company_for_job
        pass
    
    async def run(self, context: JobSearchWorkflowContext) -> JobSearchWorkflowContext:
        """Research companies for matched jobs.
        
        Args:
            context: The workflow context with run_id
            
        Returns:
            Updated context
        """
        self.logger.info("Starting research node")
        
        # Validate context
        if not self._validate_context(context):
            self.logger.error("Context validation failed")
            return context
        
        # Load matched jobs from database
        session_gen = self._get_db_session()
        session = next(session_gen)
        try:
            matched_jobs = session.query(MatchedJob).filter_by(
                run_id=context.run_id
            ).all()
            
            if not matched_jobs:
                self.logger.warning("No matched jobs found for research")
                return context
            
            self.logger.info(f"Researching {len(matched_jobs)} matched jobs")
            
            job_posting_repo = GenericRepository(session, JobPosting)
            successful = 0
            failed = 0
            
            for matched_job in matched_jobs:
                # Skip if already completed
                if matched_job.research_status == "completed":
                    successful += 1
                    continue
                
                # Skip if max retries exceeded
                if matched_job.research_attempts >= self.max_retries and matched_job.research_status == "failed":
                    failed += 1
                    continue
                
                # Get job posting
                job_posting = job_posting_repo.get(str(matched_job.job_posting_id))
                if not job_posting:
                    self.logger.error(f"Job posting {matched_job.job_posting_id} not found")
                    matched_job.research_status = "failed"
                    matched_job.research_error = f"Job posting {matched_job.job_posting_id} not found"
                    matched_job.research_attempts += 1
                    failed += 1
                    session.commit()
                    continue
                
                # Perform research
                result = await self._research_company_for_job(session, matched_job, job_posting)
                if result:
                    successful += 1
                    self.logger.info(f"Research completed for {job_posting.title} at {job_posting.company_name}")
                else:
                    failed += 1
            
            self.logger.info(f"Research completed: {successful} successful, {failed} failed")
            
        except Exception as e:
            self.logger.error(f"Failed to research companies: {e}")
            context.add_error(f"Failed to research companies: {e}")
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass
        
        self.logger.info("Research node completed")
        return context
