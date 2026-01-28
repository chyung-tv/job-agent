"""
Script to retrieve latest matched job and perform company research using Exa API.

APPROACH EXPLANATION:
We use Exa's Answer API (exa.answer()) instead of the Research API or Content API because:
1. Answer API provides a synthesized, comprehensive answer directly - no need for manual AI synthesis
2. It automatically includes citations from relevant sources
3. It's optimized for research queries and handles the entire research → synthesis pipeline
4. Simpler than Content API which would require us to retrieve content and then manually synthesize with LLM

The Answer API is perfect for our use case: researching company background, team, candidate expectations, 
and current activities - all in one comprehensive response.
"""

import os
import sys
from pathlib import Path

# Add project root to Python path if running directly
# This allows the script to work both as a module and when run directly
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.database.models import MatchedJob, JobPosting, CompanyResearch, Run
from src.database.repository import GenericRepository
from src.database.session import db_session
from sqlalchemy.orm import Session
from typing import Optional, Dict, List
from datetime import datetime
import json

from exa_py import Exa
from dotenv import load_dotenv

load_dotenv()

# Initialize Exa client
exa = Exa(api_key=os.getenv("EXA_API_KEY"))


def research_company_for_job(
    session: Session,
    matched_job: MatchedJob,
    job_posting: JobPosting,
    use_streaming: bool = False,
    max_retries: int = 3,
) -> Optional[dict]:
    """
    Research company information for a job posting using Exa's Answer API.
    Updates MatchedJob and Run status tracking.
    
    Args:
        session: SQLAlchemy database session
        matched_job: The MatchedJob object to update status for
        job_posting: The JobPosting object containing company and job details
        use_streaming: If True, use stream_answer() for real-time results; otherwise use answer()
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        dict with 'answer' (str) and 'citations' (list) keys if successful, None if failed
    """
    # Check if research already exists
    existing_research = get_research_by_job_posting(session, str(job_posting.id))
    if existing_research:
        # Research already exists, mark as completed if not already
        was_completed = matched_job.research_status == "completed"
        matched_job.research_status = "completed"
        matched_job.research_completed_at = datetime.utcnow()
        matched_job.research_error = None
        
        # Update run counters only if status changed from non-completed to completed
        if matched_job.run_id and not was_completed:
            run = session.query(Run).filter_by(id=matched_job.run_id).first()
            if run:
                run.research_completed_count += 1
                session.commit()
        
        session.commit()
        print(f"   ✓ Research already exists, using existing research")
        return {
            "answer": existing_research.research_results,
            "citations": existing_research.citations or []
        }
    
    # Update status to processing
    matched_job.research_status = "processing"
    matched_job.research_attempts += 1
    session.commit()
    
    try:
        # Construct research query
        # EXPLANATION: We ask Exa to research multiple aspects in one query:
        # - Company background and history
        # - Team structure and culture
        # - Candidate expectations (from job posting and company culture)
        # - Current activities/projects (recent news, product launches, etc.)
        query = f"""Research {job_posting.company_name}, a company hiring for the position of {job_posting.title}. 
    
Please provide comprehensive information about:
1. Company background: What does this company do? What is their mission and history?
2. Team and culture: What is the team structure like? What is the company culture?
3. Candidate expectations: Based on the job posting and company culture, what do they expect from candidates for this role?
4. Current activities: What are they currently working on? Any recent news, product launches, or major initiatives?

Focus on information that would help a candidate prepare for an interview with this company.
"""
        
        print(f"\n{'='*80}")
        print(f"RESEARCHING: {job_posting.company_name} - {job_posting.title}")
        print(f"{'='*80}\n")
        print(f"Query: {query[:200]}...\n")
        
        # EXPLANATION: Exa's stream_answer() returns chunks that can be:
        # 1. String chunks (the answer text itself)
        # 2. AnswerResult objects with answer, citations, etc.
        # We need to handle both types
        
        answer_text = ""
        citations = []
        
        # EXPLANATION: Exa's stream_answer() returns StreamChunk objects
        # Each StreamChunk has:
        # - content: The text content of this chunk (may be empty for some chunks)
        # - citations: List of citations (usually populated in final chunks)
        # - has_data: Boolean indicating if chunk has data
        
        if use_streaming:
            # EXPLANATION: stream_answer() returns a generator that yields answer chunks in real-time
            # Useful for long-running queries where you want to show progress
            print("Using streaming mode - results will appear incrementally:\n")
            
            for chunk in exa.stream_answer(query, text=True):
                # EXPLANATION: StreamChunk objects have a 'content' attribute with the text
                if hasattr(chunk, 'content') and chunk.content:
                    answer_text += chunk.content
                    print(chunk.content, end='', flush=True)
                
                # Citations are typically included in later chunks
                if hasattr(chunk, 'citations') and chunk.citations:
                    citations = chunk.citations
            
            print("\n")  # New line after streaming completes
            
        else:
            # EXPLANATION: For non-streaming, we use stream_answer() and collect all chunks silently
            # The Exa SDK's answer() method may not be available, so we use stream_answer()
            # and accumulate the results without printing incrementally
            print("Using standard mode - fetching complete answer...\n")
            
            chunk_count = 0
            for chunk in exa.stream_answer(query, text=True):
                chunk_count += 1
                # EXPLANATION: Extract content from StreamChunk objects
                if hasattr(chunk, 'content') and chunk.content:
                    answer_text += chunk.content
                
                # Extract citations if available (usually in final chunks)
                if hasattr(chunk, 'citations') and chunk.citations:
                    citations = chunk.citations
            
            if chunk_count == 0:
                print("   ⚠️  Warning: No chunks received from Exa API")
                print("   → This might mean:")
                print("     1. The company is too small/local and Exa has no information")
                print("     2. There was an API error (check API key and quota)")
                print("     3. The query needs refinement")
        
        # Display results with inline explanations
        print(f"\n{'='*80}")
        print("RESEARCH RESULTS")
        print(f"{'='*80}\n")
        print(answer_text)
        
        if citations:
            print(f"\n{'='*80}")
            print(f"SOURCES ({len(citations)} citations)")
            print(f"{'='*80}\n")
            # EXPLANATION: Citations show where the information came from
            # This helps verify credibility and allows deeper research if needed
            for i, citation in enumerate(citations, 1):
                # EXPLANATION: Citations are AnswerResult objects with url and title attributes
                url = getattr(citation, 'url', 'N/A')
                title = getattr(citation, 'title', None)
                print(f"{i}. {url}")
                if title:
                    print(f"   Title: {title}")
        
        # Save research results to database
        saved_research = save_research_results(
            session=session,
            job_posting_id=str(job_posting.id),
            company_name=job_posting.company_name,
            research_results=answer_text,
            citations=citations
        )
        
        # Update matched job status (only increment counter if status changed)
        was_completed = matched_job.research_status == "completed"
        matched_job.research_status = "completed"
        matched_job.research_completed_at = datetime.utcnow()
        matched_job.research_error = None
        
        # Update run counters only if status changed from non-completed to completed
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
        # Handle failure
        error_msg = str(e)
        matched_job.research_status = "failed" if matched_job.research_attempts >= max_retries else "pending"
        matched_job.research_error = error_msg
        
        # Update run counters (only increment failed count if marking as failed for first time)
        was_failed = matched_job.research_status == "failed"
        if matched_job.run_id and matched_job.research_attempts >= max_retries and not was_failed:
            run = session.query(Run).filter_by(id=matched_job.run_id).first()
            if run:
                run.research_failed_count += 1
                session.commit()
        
        session.commit()
        
        print(f"   ❌ Research failed (attempt {matched_job.research_attempts}/{max_retries}): {error_msg}")
        
        if matched_job.research_attempts < max_retries:
            print(f"   → Will retry later")
        else:
            print(f"   → Max retries exceeded, marking as failed")
        
        return None


# ============================================================================
# DATABASE CRUD OPERATIONS FOR COMPANY RESEARCH
# ============================================================================

def save_research_results(
    session: Session,
    job_posting_id: str,
    company_name: str,
    research_results: str,
    citations: Optional[List] = None
) -> CompanyResearch:
    """
    Save or update company research results in the database.
    
    Args:
        session: SQLAlchemy database session
        job_posting_id: UUID of the job posting (as string)
        company_name: Name of the company
        research_results: The synthesized research text
        citations: Optional list of citation objects (will be serialized to JSON)
    
    Returns:
        CompanyResearch: The saved or updated research record
    
    EXPLANATION: This function implements upsert logic - if research already exists
    for this job posting, it updates it; otherwise creates a new record.
    """
    import uuid
    
    # Convert citations to JSON-serializable format
    citations_json = None
    if citations:
        citations_list = []
        for citation in citations:
            citation_dict = {
                "url": getattr(citation, 'url', None) or str(citation.get('url', '')) if isinstance(citation, dict) else '',
                "title": getattr(citation, 'title', None) or citation.get('title', '') if isinstance(citation, dict) else ''
            }
            citations_list.append(citation_dict)
        citations_json = citations_list
    
    # Check if research already exists for this job posting
    existing_research = session.query(CompanyResearch).filter_by(
        job_posting_id=uuid.UUID(job_posting_id)
    ).first()
    
    if existing_research:
        # Update existing research
        existing_research.company_name = company_name
        existing_research.research_results = research_results
        existing_research.citations = citations_json
        existing_research.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(existing_research)
        print(f"   ✓ Updated existing research record (ID: {existing_research.id})")
        return existing_research
    else:
        # Create new research record
        new_research = CompanyResearch(
            job_posting_id=uuid.UUID(job_posting_id),
            company_name=company_name,
            research_results=research_results,
            citations=citations_json
        )
        session.add(new_research)
        session.commit()
        session.refresh(new_research)
        print(f"   ✓ Created new research record (ID: {new_research.id})")
        return new_research


def get_research_by_job_posting(
    session: Session,
    job_posting_id: str
) -> Optional[CompanyResearch]:
    """
    Retrieve company research for a specific job posting.
    
    Args:
        session: SQLAlchemy database session
        job_posting_id: UUID of the job posting (as string)
    
    Returns:
        CompanyResearch if found, None otherwise
    """
    import uuid
    
    return session.query(CompanyResearch).filter_by(
        job_posting_id=uuid.UUID(job_posting_id)
    ).first()


def research_exists(session: Session, job_posting_id: str) -> bool:
    """
    Check if research already exists for a job posting.
    
    Args:
        session: SQLAlchemy database session
        job_posting_id: UUID of the job posting (as string)
    
    Returns:
        bool: True if research exists, False otherwise
    """
    return get_research_by_job_posting(session, job_posting_id) is not None


def get_research_by_company_name(
    session: Session,
    company_name: str
) -> List[CompanyResearch]:
    """
    Retrieve all research records for a specific company.
    
    Args:
        session: SQLAlchemy database session
        company_name: Name of the company
    
    Returns:
        List of CompanyResearch records
    """
    return session.query(CompanyResearch).filter_by(
        company_name=company_name
    ).all()


def research_matched_jobs_for_run(
    session: Session,
    run_id: str,
    use_streaming: bool = False,
    max_retries: int = 3,
) -> Dict[str, int]:
    """
    Research all matched jobs for a run.
    
    Args:
        session: SQLAlchemy database session
        run_id: UUID of the run (as string)
        use_streaming: If True, use streaming mode for research
        max_retries: Maximum number of retry attempts per job
    
    Returns:
        Dictionary with counts: {'successful': int, 'failed': int, 'total': int}
    """
    import uuid
    
    # Get all matched jobs for this run
    matched_jobs = session.query(MatchedJob).filter_by(
        run_id=uuid.UUID(run_id)
    ).all()
    
    if not matched_jobs:
        print(f"No matched jobs found for run {run_id}")
        return {'successful': 0, 'failed': 0, 'total': 0}
    
    print(f"\n{'='*80}")
    print(f"RESEARCHING {len(matched_jobs)} MATCHED JOBS FOR RUN {run_id}")
    print(f"{'='*80}\n")
    
    successful = 0
    failed = 0
    
    for i, matched_job in enumerate(matched_jobs, 1):
        print(f"\n[{i}/{len(matched_jobs)}] Processing matched job {matched_job.id}")
        
        # Check if already completed (but still process to ensure status is correct)
        if matched_job.research_status == "completed":
            print("   ⏭️  Research already completed, skipping")
            successful += 1
            continue
        
        # Skip if max retries exceeded
        if matched_job.research_attempts >= max_retries and matched_job.research_status == "failed":
            print("   ⏭️  Max retries exceeded, skipping")
            failed += 1
            continue
        
        # Get job posting
        job_posting_repo = GenericRepository(session, JobPosting)
        job_posting = job_posting_repo.get(str(matched_job.job_posting_id))
        
        if not job_posting:
            print(f"   ❌ Job posting {matched_job.job_posting_id} not found")
            matched_job.research_status = "failed"
            matched_job.research_error = f"Job posting {matched_job.job_posting_id} not found"
            matched_job.research_attempts += 1
            failed += 1
            session.commit()
            continue
        
        # Perform research
        result = research_company_for_job(
            session=session,
            matched_job=matched_job,
            job_posting=job_posting,
            use_streaming=use_streaming,
            max_retries=max_retries,
        )
        
        if result:
            successful += 1
            print(f"   ✓ Research completed successfully")
        else:
            failed += 1
    
    print(f"\n{'='*80}")
    print(f"RESEARCH SUMMARY")
    print(f"{'='*80}")
    print(f"Total: {len(matched_jobs)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    
    return {
        'successful': successful,
        'failed': failed,
        'total': len(matched_jobs)
    }


if __name__ == "__main__":
    """
    EXECUTION FLOW EXPLANATION:
    1. Get database session - connects to PostgreSQL
    2. Retrieve latest matched job - gets the most recent job match from MatchedJob table
    3. Fetch original job posting - uses job_posting_id to get full JobPosting details
    4. Check if research exists - queries CompanyResearch table for existing research
    5. Perform research - calls Exa Answer API with company/job query
    6. Display results - prints research findings and citations
    7. Save to database - stores research results in CompanyResearch table for later use
    8. Clean up - properly closes database session
    
    The saved research can be cross-referenced with user profiles and used to fabricate
    tailored application materials in subsequent workflow steps.
    """
    print("="*80)
    print("JOB COMPANY RESEARCH SCRIPT")
    print("="*80)
    print("\nEXECUTION FLOW:")
    print("1. Connecting to database...")
    
    # Get database session
    session_gen = db_session()
    session = next(session_gen)
    
    try:
        print("2. Retrieving latest matched job from database...")
        # Retrieve latest matched job
        matched_job_repo = GenericRepository(session, MatchedJob)
        latest_matched_jobs = matched_job_repo.get_latest()
        
        if not latest_matched_jobs:
            print("   ❌ No matched jobs found in database")
            print("   → Make sure you have run the matching workflow first")
        else:
            latest_matched_job = latest_matched_jobs[0]
            print(f"   ✓ Found matched job ID: {latest_matched_job.id}")
            print(f"   → Job posting ID: {latest_matched_job.job_posting_id}")
            
            print("\n3. Fetching original job posting details...")
            # Retrieve original job posting
            job_posting_repo = GenericRepository(session, JobPosting)
            job_posting = job_posting_repo.get(str(latest_matched_job.job_posting_id))
            
            if not job_posting:
                print(f"   ❌ Job posting {latest_matched_job.job_posting_id} not found")
            else:
                print(f"   ✓ Retrieved job posting:")
                print(f"     - Title: {job_posting.title}")
                print(f"     - Company: {job_posting.company_name}")
                print(f"     - Location: {job_posting.location}")
                
                print("\n4. Checking if research already exists...")
                # Check if research already exists for this job posting
                existing_research = get_research_by_job_posting(
                    session, 
                    str(latest_matched_job.job_posting_id)
                )
                
                if existing_research:
                    print(f"   ⚠️  Research already exists (created: {existing_research.created_at})")
                    print("   → Will update with new research results")
                else:
                    print("   ✓ No existing research found - will create new record")
                
                print("\n5. Performing company research with Exa Answer API...")
                print("   → This may take 10-30 seconds depending on query complexity")
                
                # Perform research using Exa Answer API
                # EXPLANATION: We use standard mode (non-streaming) by default for simplicity
                # Set use_streaming=True if you want to see results incrementally
                research_result = research_company_for_job(job_posting, use_streaming=False)
                
                print("\n6. Research complete!")
                print(f"   → Answer length: {len(research_result['answer'])} characters")
                print(f"   → Sources cited: {len(research_result['citations'])}")
                
                print("\n7. Saving research results to database...")
                # Save research results to database
                # EXPLANATION: This stores the research in CompanyResearch table
                # The research can later be retrieved and cross-referenced with user profiles
                # for fabricating tailored application materials
                saved_research = save_research_results(
                    session=session,
                    job_posting_id=str(latest_matched_job.job_posting_id),
                    company_name=job_posting.company_name,
                    research_results=research_result['answer'],
                    citations=research_result['citations']
                )
                
                print(f"   ✓ Research saved successfully!")
                print(f"   → Research ID: {saved_research.id}")
                print(f"   → Can be retrieved using job_posting_id: {latest_matched_job.job_posting_id}")
                
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n8. Closing database session...")
        # Properly close the session
        try:
            next(session_gen, None)  # Consume generator to trigger commit
        except StopIteration:
            pass
        session.close()
        print("   ✓ Database session closed")


# Async version for use in async contexts (e.g., FastAPI endpoints)
async def research_job_posting_async(job_posting: JobPosting, use_streaming: bool = False) -> dict:
    """
    Async version of research_company_for_job for use in async contexts.
    
    EXPLANATION: This function can be used in FastAPI endpoints or other async code.
    Note: Exa's Python SDK methods are synchronous, so we run them in an executor
    to avoid blocking the event loop.
    """
    import asyncio
    
    # EXPLANATION: Run the synchronous Exa API call in a thread pool executor
    # This prevents blocking the async event loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: research_company_for_job(job_posting, use_streaming)
    )
