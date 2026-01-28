"""SerpAPI service factory for Google Jobs search with pagination support."""

import os
import uuid
from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from serpapi import Client
from .serpapi_models import SerpApiJobsResponse, JobResult
from dotenv import load_dotenv

if TYPE_CHECKING:
    from src.workflow.base_context import JobSearchWorkflowContext as WorkflowContext  # Alias for backward compatibility

load_dotenv()

# Optional database imports - only import if needed
try:
    from src.database import db_session, GenericRepository, JobSearch, JobPosting
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


class SerpApiJobsService:
    """Service factory for SerpAPI Google Jobs search.

    According to SerpAPI documentation:
    - Up to 10 results are returned per page
    - Use next_page_token from serpapi_pagination.next_page_token for subsequent pages
    - Do not include next_page_token in the initial request
    """

    RESULTS_PER_PAGE = 10

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the SerpAPI service.

        Args:
            api_key: SerpAPI API key. If not provided, will try to get from environment.
        """
        self.api_key = api_key or os.getenv("SERPAPI_KEY")
        if not self.api_key:
            raise ValueError(
                "SerpAPI API key is required. Provide it as argument or set SERPAPI_KEY environment variable."
            )

        self.client = Client(api_key=self.api_key)

    def _build_base_params(
        self,
        query: str,
        location: Optional[str] = None,
        google_domain: str = "google.com",
        hl: str = "en",
        gl: str = "us",
    ) -> Dict[str, Any]:
        """Build base search parameters.

        Args:
            query: Search query
            location: Optional location
            google_domain: Google domain
            hl: Language code
            gl: Country code

        Returns:
            Base parameters dictionary
        """
        params: Dict[str, Any] = {
            "engine": "google_jobs",
            "q": query,
            "google_domain": google_domain,
            "hl": hl,
            "gl": gl,
        }

        if location:
            params["location"] = location

        return params

    def _get_next_page_token(self, response: SerpApiJobsResponse) -> Optional[str]:
        """Safely extract next page token from response.
        
        This method handles all edge cases:
        - Missing serpapi_pagination attribute
        - None pagination object
        - Missing next_page_token in pagination object
        
        Args:
            response: The SerpApiJobsResponse object
            
        Returns:
            Next page token string if available, None otherwise
        """
        try:
            # Check if response has the serpapi_pagination attribute
            if not hasattr(response, 'serpapi_pagination'):
                return None
            
            # Check if pagination object exists and is not None
            pagination = response.serpapi_pagination
            if pagination is None:
                return None
            
            # Check if next_page_token exists and is not None/empty
            token = pagination.next_page_token
            if token:
                return token
            
            return None
        except (AttributeError, TypeError):
            # Handle any unexpected attribute access errors gracefully
            return None


    def _save_jobs_to_db(
        self,
        jobs: List[JobResult],
        query: str,
        location: str,
        google_domain: str,
        hl: str,
        gl: str,
        job_search_id: Optional[uuid.UUID] = None,
    ) -> Optional[uuid.UUID]:
        """Save job search results to database.
        
        Args:
            jobs: List of JobResult objects to save
            query: Search query
            location: Search location
            google_domain: Google domain used
            hl: Language code
            gl: Country code
            job_search_id: Optional existing JobSearch ID, creates new if None
            
        Returns:
            JobSearch UUID if successful, None otherwise
        """
        if not DB_AVAILABLE:
            return None
            
        session_gen = db_session()
        session = next(session_gen)
        try:
            job_search_repo = GenericRepository(session, JobSearch)
            job_posting_repo = GenericRepository(session, JobPosting)
            
            # Get or create JobSearch
            if job_search_id:
                job_search = job_search_repo.get(str(job_search_id))
                if not job_search:
                    raise ValueError(f"JobSearch with ID {job_search_id} not found")
            else:
                job_search = JobSearch(
                    id=uuid.uuid4(),
                    query=query,
                    location=location,
                    google_domain=google_domain,
                    hl=hl,
                    gl=gl,
                    total_jobs_found=len(jobs),
                )
                job_search = job_search_repo.create(job_search)
                print(f"[DATABASE] Created JobSearch: {job_search.id}")
            
            # Save each job posting
            saved_count = 0
            failed_count = 0
            for job_result in jobs:
                try:
                    # Convert Pydantic models to dict for JSON fields
                    extensions = job_result.extensions if job_result.extensions else []
                    detected_extensions = (
                        job_result.detected_extensions.model_dump()
                        if job_result.detected_extensions
                        else None
                    )
                    job_highlights = (
                        [h.model_dump() for h in job_result.job_highlights]
                        if job_result.job_highlights
                        else None
                    )
                    apply_options = (
                        [opt.model_dump() for opt in job_result.apply_options]
                        if job_result.apply_options
                        else None
                    )
                    
                    job_posting = JobPosting(
                        id=uuid.uuid4(),
                        job_search_id=job_search.id,
                        job_id=job_result.job_id,
                        title=job_result.title,
                        company_name=job_result.company_name,
                        location=job_result.location,
                        via=job_result.via,
                        share_link=job_result.share_link,
                        description=job_result.description,
                        extensions=extensions,
                        detected_extensions=detected_extensions,
                        job_highlights=job_highlights,
                        apply_options=apply_options,
                    )
                    job_posting_repo.create(job_posting)
                    saved_count += 1
                except Exception as e:
                    failed_count += 1
                    # Truncate job_id for logging if it's too long
                    job_id_display = job_result.job_id[:50] + "..." if job_result.job_id and len(job_result.job_id) > 50 else job_result.job_id
                    print(f"[WARNING] Failed to save job posting {job_id_display}: {e}")
                    # Ensure session is rolled back and ready for next operation
                    try:
                        if session.in_transaction():
                            session.rollback()
                    except Exception:
                        pass  # Session might already be rolled back or in invalid state
                    continue
            
            if failed_count > 0:
                print(f"[DATABASE] Failed to save {failed_count} job postings")
            
            print(f"[DATABASE] Saved {saved_count}/{len(jobs)} job postings")
            
            # Update job search with total count
            job_search.total_jobs_found = len(jobs)
            job_search_repo.update(job_search)
            
            return job_search.id
            
        except Exception as e:
            print(f"[ERROR] Database save failed: {e}")
            import traceback
            traceback.print_exc()
            session.rollback()
            raise e
        finally:
            try:
                next(session_gen, None)  # Consume generator to trigger commit
            except StopIteration:
                pass

    def search_jobs(
        self,
        context: "WorkflowContext",
        save_to_db: bool = True,
    ) -> "WorkflowContext":
        """Search for jobs using WorkflowContext (Context Object Pattern).
        
        Updates the context with jobs and job_search_id.
        
        Args:
            context: WorkflowContext object containing search parameters
            save_to_db: Whether to save results to database (default: True)
            
        Returns:
            Updated WorkflowContext with jobs and job_search_id populated
        """
        if not context.validate_for_discovery():
            return context
        
        all_jobs: List[JobResult] = []

        # Calculate number of pages needed (ceiling division)
        num_pages = (context.num_results + self.RESULTS_PER_PAGE - 1) // self.RESULTS_PER_PAGE

        # Get base parameters (without next_page_token)
        base_params = self._build_base_params(
            query=context.query,
            location=context.location,
            google_domain=context.google_domain,
            hl=context.hl,
            gl=context.gl,
        )

        next_page_token: Optional[str] = None

        for page_num in range(num_pages):
            # Create fresh params for this page
            params = base_params.copy()

            # Only add next_page_token for subsequent pages (not the first page)
            if next_page_token:
                params["next_page_token"] = next_page_token

            # Perform API call
            try:
                results = self.client.search(params)
            except Exception as e:
                # API call failed - log and break
                print(f"API Error fetching page {page_num + 1}: {e}")
                break

            # Parse response into model
            try:
                response = SerpApiJobsResponse.from_serpapi_results(results.as_dict())
            except Exception as e:
                # Model validation failed - log detailed error and break
                print(f"Model Validation Error on page {page_num + 1}: {e}")
                print(f"Response keys: {list(results.as_dict().keys()) if hasattr(results, 'as_dict') else 'N/A'}")
                break

            # Add jobs from this page
            if response.jobs_results:
                all_jobs.extend(response.jobs_results)

            # Check if we have enough results
            if len(all_jobs) >= context.num_results:
                all_jobs = all_jobs[:context.num_results]
                # Break early but still save to DB below
                break

            # Check if there's a next page available using safe helper method
            next_page_token = self._get_next_page_token(response)
            if not next_page_token:
                # No more pages available
                break

        # Save to database if requested
        saved_job_search_id = context.job_search_id
        if save_to_db and DB_AVAILABLE and all_jobs:
            try:
                saved_job_search_id = self._save_jobs_to_db(
                    jobs=all_jobs,
                    query=context.query,
                    location=context.location or "",
                    google_domain=context.google_domain,
                    hl=context.hl,
                    gl=context.gl,
                    job_search_id=context.job_search_id,
                )
            except Exception as e:
                context.add_error(f"Failed to save jobs to database: {e}")
                print(f"[WARNING] Failed to save jobs to database: {e}")
                # Continue execution even if database save fails
        
        context.jobs = all_jobs
        context.job_search_id = saved_job_search_id
        
        return context

    @classmethod
    def create(cls, api_key: Optional[str] = None) -> "SerpApiJobsService":
        """Factory method to create a SerpAPI service instance.

        Args:
            api_key: Optional API key. If not provided, will try to get from environment.

        Returns:
            SerpApiJobsService instance
        """
        return cls(api_key=api_key)
