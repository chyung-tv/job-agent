"""Central workflow orchestration for job search, profiling, and matching pipeline."""

from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import nest_asyncio

from src.discovery.serpapi_service import SerpApiJobsService
from src.discovery.serpapi_models import JobResult
from src.profiling.profile import build_user_profile
from src.matcher.matcher import JobScreeningAgent, JobScreeningOutput
from src.workflow.context import WorkflowContext

nest_asyncio.apply()
load_dotenv()


def display_jobs(jobs: list[JobResult], max_display: int = 5) -> None:
    """Display job listings.

    Args:
        jobs: List of jobs to display
        max_display: Maximum number of jobs to display
    """
    print("\nJob Listings:")
    print("-" * 80)
    for i, job in enumerate(jobs[:max_display], 1):
        print(f"\n{i}. {job.title or 'N/A'}")
        print(f"   Company: {job.company_name or 'N/A'}")
        print(f"   Location: {job.location or 'N/A'}")
        print(f"   Via: {job.via or 'N/A'}")
        if job.description:
            desc_preview = (
                job.description[:150] + "..."
                if len(job.description) > 150
                else job.description
            )
            print(f"   Description: {desc_preview}")
        if job.job_id:
            print(f"   Job ID: {job.job_id}")


def display_matched_jobs(matched_results: list[JobScreeningOutput]) -> None:
    """Display matched jobs details.

    Args:
        matched_results: List of job screening results to display
    """
    if not matched_results:
        return

    print(f"\n{'=' * 80}")
    print("Matched Jobs Details:")
    print("=" * 80)
    for result in matched_results:
        print(f"\n• {result.job_title}")
        print(f"  Company: {result.job_company}")
        print(f"  Location: {result.job_location}")
        print(f"  Job ID: {result.job_id}")
        print(f"  Reason: {result.reason}")
        if result.application_link:
            print(f"  Apply via: {result.application_link.get('via', 'N/A')}")
            print(f"  Apply link: {result.application_link.get('link', 'N/A')}")
        if len(result.job_description) > 150:
            desc_preview = result.job_description[:150] + "..."
            print(f"  Description: {desc_preview}")
        else:
            print(f"  Description: {result.job_description}")


def run(
    query: str,
    location: str,
    num_results: int = 30,
    max_screening: int = 5,
    pdf_paths: Optional[list[Path]] = None,
    data_dir: Optional[Path] = None,
    google_domain: str = "google.com",
    hl: str = "en",
    gl: str = "us",
) -> WorkflowContext:
    """Run the complete workflow using Context Object Pattern.
    
    This implementation uses WorkflowContext to carry state through the pipeline,
    improving modularity and making it easier to extend the workflow with new steps.
    
    Workflow steps:
    1. Discovery: Search for jobs using SerpAPI
    2. Profiling: Extract and build user profile from PDF documents
    3. Matching: Screen jobs using AI agent against user profile
    4. Display: Show matched jobs
    
    Args:
        query: Job search query (e.g., "software engineer", "ai developer")
        location: Location for the search (e.g., "Hong Kong")
        num_results: Number of job results to fetch (default: 30)
        max_screening: Maximum number of jobs to screen (default: 5)
        pdf_paths: Optional list of specific PDF paths to parse for profiling.
                   If None, will look for common files in data_dir.
        data_dir: Directory to search for PDFs if pdf_paths not provided.
        google_domain: Google domain to use (default: "google.com")
        hl: Language code (default: "en")
        gl: Country code (default: "us")
    
    Returns:
        WorkflowContext object with all workflow state populated
    """
    # Create initial context
    context = WorkflowContext(
        query=query,
        location=location,
        num_results=num_results,
        max_screening=max_screening,
        pdf_paths=pdf_paths,
        data_dir=data_dir,
        google_domain=google_domain,
        hl=hl,
        gl=gl,
    )
    
    # Step 1: Discovery - Search for jobs
    print("=" * 80)
    print("STEP 1: DISCOVERY - Searching for jobs...")
    print("=" * 80)
    print(f"Query: {context.query}")
    print(f"Location: {context.location}\n")
    
    service = SerpApiJobsService.create()
    context = service.search_jobs(context, save_to_db=True)
    
    print(f"Found {len(context.jobs)} jobs\n")
    if context.job_search_id:
        print(f"[DATABASE] Saved job search with ID: {context.job_search_id}\n")
    display_jobs(context.jobs, max_display=5)
    
    # Step 2: Profiling - Build user profile from PDFs
    print("\n" + "=" * 80)
    print("STEP 2: PROFILING - Building user profile from documents...")
    print("=" * 80)
    
    try:
        context = build_user_profile(context)
        
        # Check if profile was actually built
        if not context.user_profile:
            context.add_error("Profile building completed but profile is empty")
            print("\n[ERROR] Profile is empty - check PDF files and try again")
            raise ValueError("Profile is empty")
        
        if context.profile_was_cached:
            print(
                f"\n[SUCCESS] Profile loaded from cache ({len(context.user_profile)} characters)"
            )
        else:
            print(
                f"\n[SUCCESS] Profile built successfully ({len(context.user_profile)} characters)"
            )
    except Exception as e:
        context.add_error(f"Failed to build profile: {e}")
        print(f"\n[ERROR] Failed to build profile: {e}")
        raise
    
    # Step 3: Matching - Screen jobs using AI agent
    print("\n" + "=" * 80)
    print("STEP 3: MATCHING - Screening jobs against user profile...")
    print("=" * 80)
    
    screening_agent = JobScreeningAgent()
    context = screening_agent.screen_jobs(
        context,
        verbose=True,
        save_to_db=True,
    )
    
    # Update JobSearch with final statistics
    if context.job_search_id:
        try:
            from src.database import db_session, GenericRepository, JobSearch
            
            session = next(db_session())
            try:
                job_search_repo = GenericRepository(session, JobSearch)
                job_search = job_search_repo.get(str(context.job_search_id))
                if job_search:
                    job_search.jobs_screened = len(context.all_screening_results)
                    job_search.matches_found = len(context.matched_results)
                    job_search_repo.update(job_search)
                    print("\n[DATABASE] Updated job search statistics")
            finally:
                session.close()
        except Exception as e:
            context.add_error(f"Failed to update job search statistics: {e}")
            print(f"[WARNING] Failed to update job search statistics: {e}")
    
    # Step 4: Display summary and matched jobs
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print("=" * 80)
    print(f"Total jobs found: {len(context.jobs)}")
    print(f"Jobs screened: {len(context.all_screening_results)}")
    print(f"Matches found: {len(context.matched_results)}")
    
    display_matched_jobs(context.matched_results)
    
    return context


def main():
    """Main entry point for the workflow."""
    context = run(
        query="software engineer",
        location="Hong Kong",
        num_results=30,
        max_screening=3,
    )

    return context.matched_results


if __name__ == "__main__":
    main()
