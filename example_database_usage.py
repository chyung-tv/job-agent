"""Example script demonstrating database usage with the Repository pattern."""

import uuid
from datetime import datetime

from src.database import (
    db_session,
    GenericRepository,
    JobSearch,
    JobPosting,
    MatchedJob,
)


def example_create_job_search():
    """Example: Create a new job search workflow."""
    session = next(db_session())
    job_search_repo = GenericRepository(session, JobSearch)
    
    # Create a new job search
    new_search = JobSearch(
        id=uuid.uuid4(),
        query="software engineer",
        location="Hong Kong",
        google_domain="google.com",
        hl="en",
        gl="us",
        total_jobs_found=30,
        jobs_screened=5,
        matches_found=2,
    )
    
    created_search = job_search_repo.create(new_search)
    print(f"✓ Created job search with ID: {created_search.id}")
    
    session.close()
    return created_search


def example_create_job_posting(job_search_id: uuid.UUID):
    """Example: Create a job posting linked to a job search."""
    session = next(db_session())
    job_posting_repo = GenericRepository(session, JobPosting)
    
    # Create a new job posting
    new_posting = JobPosting(
        id=uuid.uuid4(),
        job_search_id=job_search_id,
        job_id="serpapi_job_123",
        title="Senior Software Engineer",
        company_name="Tech Corp",
        location="Hong Kong",
        via="LinkedIn",
        description="We are looking for a senior software engineer...",
        extensions=["Full-time", "Remote"],
        apply_options=[{"title": "Apply on LinkedIn", "link": "https://..."}],
    )
    
    created_posting = job_posting_repo.create(new_posting)
    print(f"✓ Created job posting with ID: {created_posting.id}")
    
    session.close()
    return created_posting


def example_create_matched_job(
    job_search_id: uuid.UUID, job_posting_id: uuid.UUID
):
    """Example: Create a matched job record."""
    session = next(db_session())
    matched_job_repo = GenericRepository(session, MatchedJob)
    
    # Create a matched job
    new_match = MatchedJob(
        id=uuid.uuid4(),
        job_search_id=job_search_id,
        job_posting_id=job_posting_id,
        is_match=True,
        reason="Strong match: User has 5+ years of Python experience and relevant domain knowledge.",
        job_description_summary="Senior role requiring Python, FastAPI, and cloud experience.",
        application_link={"via": "LinkedIn", "link": "https://..."},
    )
    
    created_match = matched_job_repo.create(new_match)
    print(f"✓ Created matched job with ID: {created_match.id}")
    
    session.close()
    return created_match


def example_query_job_searches():
    """Example: Query job searches."""
    session = next(db_session())
    job_search_repo = GenericRepository(session, JobSearch)
    
    # Get all job searches
    all_searches = job_search_repo.get_all()
    print(f"\nTotal job searches: {len(all_searches)}")
    
    # Get latest 5 searches
    latest_searches = job_search_repo.get_latest(5)
    print(f"\nLatest 5 searches:")
    for search in latest_searches:
        print(f"  - {search.query} in {search.location} ({search.matches_found} matches)")
    
    # Filter by location
    hk_searches = job_search_repo.filter_by(location="Hong Kong")
    print(f"\nSearches in Hong Kong: {len(hk_searches)}")
    
    session.close()


def example_query_with_relationships():
    """Example: Query with relationships."""
    session = next(db_session())
    job_search_repo = GenericRepository(session, JobSearch)
    
    # Get a job search with its related job postings
    searches = job_search_repo.get_all()
    if searches:
        search = searches[0]
        print(f"\nJob Search: {search.query} in {search.location}")
        print(f"  Total jobs found: {search.total_jobs_found}")
        print(f"  Job postings: {len(search.job_postings)}")
        print(f"  Matched jobs: {len(search.matched_jobs)}")
        
        # Show first few job postings
        for posting in search.job_postings[:3]:
            print(f"    - {posting.title} at {posting.company_name}")
    
    session.close()


def main():
    """Run all examples."""
    print("=" * 80)
    print("Database Usage Examples")
    print("=" * 80)
    
    # Example 1: Create job search
    print("\n1. Creating job search...")
    job_search = example_create_job_search()
    
    # Example 2: Create job posting
    print("\n2. Creating job posting...")
    job_posting = example_create_job_posting(job_search.id)
    
    # Example 3: Create matched job
    print("\n3. Creating matched job...")
    matched_job = example_create_matched_job(job_search.id, job_posting.id)
    
    # Example 4: Query job searches
    print("\n4. Querying job searches...")
    example_query_job_searches()
    
    # Example 5: Query with relationships
    print("\n5. Querying with relationships...")
    example_query_with_relationships()
    
    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
