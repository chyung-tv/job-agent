"""Matching node for screening jobs against user profiles."""

import uuid
import hashlib
from typing import List, Optional
import logging

from pydantic_ai import Agent
from pydantic import BaseModel, Field
from src.discovery.serpapi_models import JobResult

from src.workflow.base_node import BaseNode
from src.workflow.base_context import JobSearchWorkflowContext
from src.config import LangfuseConfig
from src.langfuse_utils import create_workflow_trace_context, propagate_attributes

# Import JobScreeningOutput from matcher to match context expectations
from src.matcher.matcher import JobScreeningOutput as MatcherJobScreeningOutput
from src.database import (
    db_session,
    GenericRepository,
    MatchedJob,
    JobPosting,
    JobSearch,
)
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
langfuse_config = LangfuseConfig.from_env()


# Use JobScreeningOutput from matcher module to maintain compatibility
JobScreeningOutput = MatcherJobScreeningOutput


class MatchingNode(BaseNode):
    """Node for matching jobs against user profiles using AI."""

    def __init__(self, model: str = "google-gla:gemini-2.5-flash"):
        """Initialize the matching node.

        Args:
            model: The AI model to use for job matching
        """
        super().__init__()
        self.agent = Agent(
            model=model,
            output_type=JobScreeningOutput,
            instrument=langfuse_config.enabled,
        )

    def _validate_context(self, context: JobSearchWorkflowContext) -> bool:
        """Validate required context fields for matching.

        Args:
            context: The workflow context

        Returns:
            True if valid, False otherwise
        """
        if not context.user_profile:
            context.add_error("User profile is required for matching step")
            return False
        if not context.jobs and not context.job_search_id:
            context.add_error(
                "Jobs list or job_search_id is required for matching step"
            )
            return False
        return True

    def _build_prompt(self, user_profile: str, job: JobResult) -> str:
        """Build the prompt for job matching.

        Args:
            user_profile: The user's profile/skills description
            job: The job posting to match

        Returns:
            Formatted prompt string
        """
        return f"""You are a job matcher. Analyze if a job posting matches a user profile.

User profile: {user_profile}

Job posting:
- Job ID: {job.job_id or "N/A"}
- Title: {job.title or "N/A"}
- Company: {job.company_name or "N/A"}
- Location: {job.location or "N/A"}
- Description: {job.description or "N/A"}

Return a structured response with:
- job_id: REQUIRED - The exact job ID from the posting above: "{job.job_id or "N/A"}"
- job_title: The job title
- job_company: The company name
- job_location: The job location
- job_description: A summary of the job description (max 200 words)
- is_match: True if the job matches the user profile and skills, False otherwise
- reason: REQUIRED - A detailed explanation for why it matches or doesn't match. 
  If it doesn't match, explain what skills/experience are missing or what requirements are not met.
  If it matches, explain which skills/experience align well.
- application_link: Optional dict with "via" (application platform) and "link" (application URL) keys

IMPORTANT: 
- Always use the exact job_id provided above: "{job.job_id or "N/A"}"
- Always provide a detailed reason, whether the job matches or not.
"""

    async def _match_job(
        self,
        user_profile: str,
        job: JobResult,
        context: JobSearchWorkflowContext,
    ) -> Optional[JobScreeningOutput]:
        """Match a single job against a user profile.

        Args:
            user_profile: The user's profile/skills description
            job: The job posting to match
            context: Workflow context for trace propagation

        Returns:
            JobScreeningOutput if successful, None if job is invalid or matching fails
        """
        if not job.title or not job.job_id:
            return None

        try:
            trace_context = create_workflow_trace_context(
                execution_id=str(context.run_id) if context.run_id else None,
                run_id=str(context.run_id) if context.run_id else None,
                workflow_type="job_search",
                node_name="MatchingNode",
                metadata={
                    "job_id": job.job_id,
                    "job_title": job.title,
                    "company_name": job.company_name,
                },
            )
            with propagate_attributes(**trace_context):
                prompt = self._build_prompt(user_profile, job)
                result = await self.agent.run(prompt)
                output = result.output
            # Ensure job_id is set from original job if AI didn't return it correctly
            if not output.job_id or output.job_id.strip() == "":
                output.job_id = job.job_id
            # Ensure reason is always present
            if not output.reason or output.reason.strip() == "":
                output.reason = (
                    "AI agent did not provide a reason for this match decision."
                )
            return output
        except Exception as e:
            self.logger.warning(f"Failed to match job {job.job_id}: {e}")
            return None

    def _load_data(self, context: JobSearchWorkflowContext, session) -> None:
        """Load job postings from database if jobs are not in context.

        Args:
            context: The workflow context
            session: Database session
        """
        if not context.jobs and context.job_search_id:
            job_posting_repo = GenericRepository(session, JobPosting)
            postings = job_posting_repo.filter_by(job_search_id=context.job_search_id)

            # Convert JobPosting to JobResult format
            from src.discovery.serpapi_models import JobResult

            context.jobs = []
            for posting in postings:
                job_result = JobResult(
                    job_id=posting.job_id,
                    title=posting.title,
                    company_name=posting.company_name,
                    location=posting.location,
                    via=posting.via,
                    share_link=posting.share_link,
                    description=posting.description,
                )
                context.jobs.append(job_result)

            self.logger.info(f"Loaded {len(context.jobs)} jobs from database")

    def _persist_data(self, context: JobSearchWorkflowContext, session) -> None:
        """Save matched job results to database.

        Args:
            context: The workflow context with matching results
            session: Database session
        """
        if not context.matched_results or not context.job_search_id:
            self.logger.warning("No matched results or job_search_id to persist")
            return

        matched_job_repo = GenericRepository(session, MatchedJob)
        job_posting_repo = GenericRepository(session, JobPosting)

        # Build mapping: job_id (str) -> JobPosting.id (UUID)
        postings = job_posting_repo.filter_by(job_search_id=context.job_search_id)
        job_id_to_posting_id = {
            posting.job_id: posting.id for posting in postings if posting.job_id
        }

        self.logger.info(f"Found {len(job_id_to_posting_id)} job postings in database")

        saved_count = 0
        skipped_count = 0

        for screening_output in context.matched_results:
            # Handle missing job_id by generating one from application_link
            job_id_to_use = screening_output.job_id
            if not job_id_to_use or job_id_to_use.strip() == "":
                if (
                    screening_output.application_link
                    and screening_output.application_link.get("link")
                ):
                    link_str = screening_output.application_link["link"]
                    job_id_to_use = hashlib.sha256(link_str.encode()).hexdigest()[:64]
                    self.logger.info(
                        f"Generated job_id from application_link for: {screening_output.job_title}"
                    )
                else:
                    self.logger.warning(
                        f"Matched job missing job_id and application_link, skipping: {screening_output.job_title}"
                    )
                    skipped_count += 1
                    continue

            # Find JobPosting UUID using job_id
            job_posting_id = job_id_to_posting_id.get(job_id_to_use)

            # Fallback: Try to find by title + company if job_id lookup failed
            if not job_posting_id:
                for posting in postings:
                    if (
                        posting.title == screening_output.job_title
                        and posting.company_name == screening_output.job_company
                    ):
                        job_posting_id = posting.id
                        self.logger.info(
                            f"Found JobPosting by title+company match for: {screening_output.job_title}"
                        )
                        break

            if not job_posting_id:
                self.logger.warning(
                    f"JobPosting not found for job_id: {job_id_to_use} (title: {screening_output.job_title})"
                )
                skipped_count += 1
                continue

            try:
                # Create MatchedJob record
                matched_job = MatchedJob(
                    id=uuid.uuid4(),
                    job_search_id=context.job_search_id,
                    job_posting_id=job_posting_id,
                    is_match=screening_output.is_match,
                    reason=screening_output.reason,
                    job_description_summary=screening_output.job_description,
                    application_link=screening_output.application_link,
                    run_id=context.run_id,
                )
                matched_job_repo.create(matched_job)
                saved_count += 1
            except Exception as e:
                job_id_display = (
                    job_id_to_use[:50] + "..."
                    if job_id_to_use and len(job_id_to_use) > 50
                    else (job_id_to_use or "N/A")
                )
                self.logger.warning(f"Failed to save matched job {job_id_display}: {e}")
                skipped_count += 1

        self.logger.info(
            f"Saved {saved_count}/{len(context.matched_results)} matched jobs"
        )
        if skipped_count > 0:
            self.logger.warning(f"Skipped {skipped_count} matched jobs")

        # Update JobSearch statistics
        job_search_repo = GenericRepository(session, JobSearch)
        job_search = job_search_repo.get(str(context.job_search_id))
        if job_search:
            job_search.jobs_screened = len(context.all_screening_results)
            job_search.matches_found = len(context.matched_results)
            job_search_repo.update(job_search)

    async def _execute(
        self, context: JobSearchWorkflowContext
    ) -> JobSearchWorkflowContext:
        """Screen jobs against user profile.

        Args:
            context: The workflow context with user_profile and jobs

        Returns:
            Updated context with matching results
        """
        self.logger.info("Starting matching node")

        # Validate context
        if not self._validate_context(context):
            self.logger.error("Context validation failed")
            return context

        # Load jobs from database if needed
        session_gen = self._get_db_session()
        session = next(session_gen)
        try:
            self._load_data(context, session)
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass

        if not context.jobs:
            context.add_error("No jobs available for matching")
            self.logger.error("No jobs available for matching")
            return context

        # Screen jobs
        jobs_to_screen = (
            context.jobs[: context.max_screening]
            if context.max_screening
            else context.jobs
        )
        matched_results: List[JobScreeningOutput] = []
        all_screening_results: List[JobScreeningOutput] = []

        self.logger.info(f"Matching {len(jobs_to_screen)} jobs against user profile...")

        for job in jobs_to_screen:
            result = await self._match_job(context.user_profile, job, context)
            if not result:
                continue

            all_screening_results.append(result)

            status = "MATCH" if result.is_match else "No match"
            self.logger.info(f"{status} - {result.job_title} at {result.job_company}")

            if result.is_match:
                matched_results.append(result)

        # Update context
        context.matched_results = matched_results
        context.all_screening_results = all_screening_results

        # Persist to database
        if context.job_search_id:
            session_gen = self._get_db_session()
            session = next(session_gen)
            try:
                self._persist_data(context, session)
            except Exception as e:
                self.logger.error(f"Failed to persist matched jobs: {e}")
                context.add_error(f"Failed to save matched jobs to database: {e}")
            finally:
                try:
                    next(session_gen, None)
                except StopIteration:
                    pass

        self.logger.info(
            f"Matching node completed: {len(matched_results)} matches found"
        )
        return context
