"""Discovery node for job search using SerpAPI."""

import os
import uuid
from typing import List, Optional, Dict, Any
import logging

from serpapi import Client
from src.discovery.serpapi_models import SerpApiJobsResponse, JobResult
from src.workflow.base_node import BaseNode
from src.workflow.base_context import JobSearchWorkflowContext
from src.database import db_session, GenericRepository, JobSearch, JobPosting
from src.config import RESULTS_PER_PAGE
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DiscoveryNode(BaseNode):
    """Node for discovering jobs using SerpAPI Google Jobs search."""

    RESULTS_PER_PAGE = RESULTS_PER_PAGE

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the discovery node.

        Args:
            api_key: SerpAPI API key. If not provided, will try to get from environment.
        """
        super().__init__()
        self.api_key = api_key or os.getenv("SERPAPI_KEY")
        if not self.api_key:
            raise ValueError(
                "SerpAPI API key is required. Provide it as argument or set SERPAPI_KEY environment variable."
            )
        self.client = Client(api_key=self.api_key)

    def _validate_context(self, context: JobSearchWorkflowContext) -> bool:
        """Validate required context fields for discovery.

        Args:
            context: The workflow context

        Returns:
            True if valid, False otherwise
        """
        if not context.query or not context.query.strip():
            context.add_error("Query is required for discovery step")
            return False
        if not context.location or not context.location.strip():
            context.add_error("Location is required for discovery step")
            return False
        return True

    def _load_data(self, context: JobSearchWorkflowContext, session) -> None:
        """Load existing JobSearch if job_search_id is present.

        Args:
            context: The workflow context
            session: Database session
        """
        if context.job_search_id:
            job_search_repo = GenericRepository(session, JobSearch)
            job_search = job_search_repo.get(str(context.job_search_id))
            if job_search:
                self.logger.info(f"Loaded existing JobSearch: {context.job_search_id}")
                # Load job postings if needed
                job_posting_repo = GenericRepository(session, JobPosting)
                postings = job_posting_repo.filter_by(
                    job_search_id=context.job_search_id
                )
                # Convert to JobResult format if needed
                # For now, we'll re-fetch from API if jobs are not in context
                if not context.jobs:
                    self.logger.info("No jobs in context, will fetch from API")

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

        Args:
            response: The SerpApiJobsResponse object

        Returns:
            Next page token string if available, None otherwise
        """
        try:
            if not hasattr(response, "serpapi_pagination"):
                return None

            pagination = response.serpapi_pagination
            if pagination is None:
                return None

            token = pagination.next_page_token
            if token:
                return token

            return None
        except (AttributeError, TypeError):
            return None

    def _persist_data(self, context: JobSearchWorkflowContext, session) -> None:
        """Save job search results to database.

        Args:
            context: The workflow context with jobs
            session: Database session
        """
        if not context.jobs:
            self.logger.warning("No jobs to persist")
            return

        job_search_repo = GenericRepository(session, JobSearch)
        job_posting_repo = GenericRepository(session, JobPosting)

        # Get or create JobSearch
        if context.job_search_id:
            job_search = job_search_repo.get(str(context.job_search_id))
            if not job_search:
                raise ValueError(f"JobSearch with ID {context.job_search_id} not found")
        else:
            job_search = JobSearch(
                id=uuid.uuid4(),
                query=context.query,
                location=context.location,
                google_domain=context.google_domain,
                hl=context.hl,
                gl=context.gl,
                total_jobs_found=len(context.jobs),
            )
            job_search = job_search_repo.create(job_search)
            context.job_search_id = job_search.id
            self.logger.info(f"Created JobSearch: {job_search.id}")

        # Save each job posting
        saved_count = 0
        failed_count = 0
        for job_result in context.jobs:
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
                job_id_display = (
                    job_result.job_id[:50] + "..."
                    if job_result.job_id and len(job_result.job_id) > 50
                    else (job_result.job_id or "N/A")
                )
                self.logger.warning(f"Failed to save job posting {job_id_display}: {e}")
                try:
                    if session.in_transaction():
                        session.rollback()
                except Exception:
                    pass
                continue

        if failed_count > 0:
            self.logger.warning(f"Failed to save {failed_count} job postings")

        self.logger.info(f"Saved {saved_count}/{len(context.jobs)} job postings")

        # Update job search with total count
        job_search.total_jobs_found = len(context.jobs)
        job_search_repo.update(job_search)

    async def _execute(
        self, context: JobSearchWorkflowContext
    ) -> JobSearchWorkflowContext:
        """Discover jobs using SerpAPI.

        Args:
            context: The workflow context with search parameters

        Returns:
            Updated context with jobs and job_search_id
        """
        self.logger.info("Starting discovery node")

        # Validate context
        if not self._validate_context(context):
            self.logger.error("Context validation failed")
            return context

        # Load existing data if needed
        session_gen = self._get_db_session()
        session = next(session_gen)
        try:
            self._load_data(context, session)
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass

        # If we already have jobs, skip API call
        if context.jobs:
            self.logger.info(f"Using existing {len(context.jobs)} jobs from context")
        else:
            # Fetch jobs from API
            all_jobs: List[JobResult] = []

            # Calculate number of pages needed (ceiling division)
            num_pages = (
                context.num_results + self.RESULTS_PER_PAGE - 1
            ) // self.RESULTS_PER_PAGE

            # Get base parameters
            base_params = self._build_base_params(
                query=context.query,
                location=context.location,
                google_domain=context.google_domain,
                hl=context.hl,
                gl=context.gl,
            )

            next_page_token: Optional[str] = None

            for page_num in range(num_pages):
                params = base_params.copy()

                if next_page_token:
                    params["next_page_token"] = next_page_token

                # Perform API call (synchronous, but we're in async function)
                try:
                    results = self.client.search(params)
                except Exception as e:
                    self.logger.error(f"API Error fetching page {page_num + 1}: {e}")
                    context.add_error(f"API Error fetching page {page_num + 1}: {e}")
                    break

                # Parse response into model
                try:
                    response = SerpApiJobsResponse.from_serpapi_results(
                        results.as_dict()
                    )
                except Exception as e:
                    self.logger.error(
                        f"Model Validation Error on page {page_num + 1}: {e}"
                    )
                    context.add_error(
                        f"Model Validation Error on page {page_num + 1}: {e}"
                    )
                    break

                # Add jobs from this page
                if response.jobs_results:
                    all_jobs.extend(response.jobs_results)

                # Check if we have enough results
                if len(all_jobs) >= context.num_results:
                    all_jobs = all_jobs[: context.num_results]
                    break

                # Check if there's a next page
                next_page_token = self._get_next_page_token(response)
                if not next_page_token:
                    break

            context.jobs = all_jobs
            self.logger.info(f"Found {len(all_jobs)} jobs")

        # Persist to database
        session_gen = self._get_db_session()
        session = next(session_gen)
        try:
            self._persist_data(context, session)
        except Exception as e:
            self.logger.error(f"Failed to persist data: {e}")
            context.add_error(f"Failed to save jobs to database: {e}")
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass

        self.logger.info("Discovery node completed")
        return context
