"""Job screening module using AI agent for matching jobs to user profiles."""

import uuid
import hashlib
from typing import List, Optional, TypedDict, TYPE_CHECKING
from pydantic_ai import Agent
from pydantic import BaseModel, Field
from src.discovery.serpapi_models import JobResult
from dotenv import load_dotenv
import nest_asyncio

load_dotenv()
nest_asyncio.apply()

# Optional database imports - only import if needed
try:
    from src.database import db_session, GenericRepository, MatchedJob, JobPosting, JobSearch
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

if TYPE_CHECKING:
    from src.workflow.context import WorkflowContext


class ApplicationLinkType(TypedDict):
    """Type definition for application link with via and link."""

    via: str
    link: str


class JobScreeningOutput(BaseModel):
    """Output model for job screening results."""

    job_id: str
    job_title: str
    job_company: str
    job_location: str
    job_description: str
    is_match: bool
    reason: str
    application_link: Optional[ApplicationLinkType] = Field(default=None)


class JobScreeningAgent:
    """AI-powered job screening agent for matching jobs to user profiles."""

    def __init__(self, model: str = "google-gla:gemini-2.5-flash"):
        """Initialize the job screening agent.

        Args:
            model: The AI model to use for job matching
        """
        self.agent = Agent(model=model, output_type=JobScreeningOutput)

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
- job_id: REQUIRED - The exact job ID from the posting above: "{job.job_id or 'N/A'}"
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
- Always use the exact job_id provided above: "{job.job_id or 'N/A'}"
- Always provide a detailed reason, whether the job matches or not.
"""

    def match_job(
        self, user_profile: str, job: JobResult
    ) -> Optional[JobScreeningOutput]:
        """Match a single job against a user profile.

        Args:
            user_profile: The user's profile/skills description
            job: The job posting to match

        Returns:
            JobScreeningOutput if successful, None if job is invalid or matching fails
        """
        if not job.title or not job.job_id:
            return None

        try:
            prompt = self._build_prompt(user_profile, job)
            result = self.agent.run_sync(prompt)
            output = result.output
            # Ensure job_id is set from original job if AI didn't return it correctly
            if not output.job_id or output.job_id.strip() == "":
                output.job_id = job.job_id
            # Ensure reason is always present
            if not output.reason or output.reason.strip() == "":
                output.reason = "AI agent did not provide a reason for this match decision."
            return output
        except Exception as e:
            # Log the error for debugging but still return None
            print(f"[WARNING] Failed to match job {job.job_id}: {e}")
            return None

    def screen_jobs(
        self,
        context: "WorkflowContext",
        max_jobs: Optional[int] = None,
        verbose: bool = True,
        save_to_db: bool = True,
    ) -> "WorkflowContext":
        """Screen jobs using WorkflowContext (Context Object Pattern).
        
        Updates the context with matched_results and all_screening_results.
        
        Args:
            context: WorkflowContext object containing user_profile and jobs
            max_jobs: Maximum number of jobs to screen (None for all, uses context.max_screening if None)
            verbose: Whether to print matching progress
            save_to_db: Whether to save matched jobs to database (default: True)
            
        Returns:
            Updated WorkflowContext with matching results populated
        """
        if not context.validate_for_matching():
            return context
        
        # Use context.max_screening if max_jobs not provided
        if max_jobs is None:
            max_jobs = context.max_screening
        
        jobs_to_screen = context.jobs[:max_jobs] if max_jobs else context.jobs
        matched_results: List[JobScreeningOutput] = []
        all_screening_results: List[JobScreeningOutput] = []
        
        if verbose:
            print(f"\nMatching {len(jobs_to_screen)} jobs against user profile...\n")
        
        for job in jobs_to_screen:
            result = self.match_job(context.user_profile, job)
            if not result:
                continue
            
            all_screening_results.append(result)
            
            if verbose:
                status = "✓ MATCH" if result.is_match else "✗ No match"
                print(f"{status} - {result.job_title} at {result.job_company}")
                if result.reason:
                    print(f"  Reason: {result.reason}")
            
            if result.is_match:
                matched_results.append(result)
        
        # Save matched jobs to database
        if save_to_db and DB_AVAILABLE and context.job_search_id and matched_results:
            try:
                self._save_matched_jobs_to_db(
                    matched_results=matched_results,
                    all_screening_results=all_screening_results,
                    jobs=jobs_to_screen,
                    job_search_id=context.job_search_id,
                )
            except Exception as e:
                print(f"[WARNING] Failed to save matched jobs to database: {e}")
                import traceback
                traceback.print_exc()
        
        context.matched_results = matched_results
        context.all_screening_results = all_screening_results
        
        return context

    def _save_matched_jobs_to_db(
        self,
        matched_results: List[JobScreeningOutput],
        all_screening_results: List[JobScreeningOutput],
        jobs: List[JobResult],
        job_search_id: uuid.UUID,
    ) -> None:
        """Save matched job results to database.
        
        Builds mapping from JobResult.job_id to JobPosting.id by querying the database.
        
        Args:
            matched_results: List of JobScreeningOutput objects that matched
            all_screening_results: List of all JobScreeningOutput objects (matches + non-matches)
            jobs: List of original JobResult objects (used to build job_id mapping)
            job_search_id: JobSearch ID to link matched jobs to
        """
        if not DB_AVAILABLE:
            return
            
        session_gen = db_session()
        session = next(session_gen)
        try:
            matched_job_repo = GenericRepository(session, MatchedJob)
            job_posting_repo = GenericRepository(session, JobPosting)
            
            # Build mapping: job_id (str) -> JobPosting.id (UUID)
            # Get all job postings for this search
            postings = job_posting_repo.filter_by(job_search_id=job_search_id)
            job_id_to_posting_id = {
                posting.job_id: posting.id
                for posting in postings
                if posting.job_id  # Only include postings with job_id
            }
            
            print(f"[DATABASE] Found {len(job_id_to_posting_id)} job postings in database")
            
            saved_count = 0
            skipped_count = 0
            
            for screening_output in matched_results:
                # Handle missing job_id by generating one from application_link
                job_id_to_use = screening_output.job_id
                if not job_id_to_use or job_id_to_use.strip() == "":
                    if screening_output.application_link and screening_output.application_link.get("link"):
                        # Generate a unique ID from application_link
                        link_str = screening_output.application_link["link"]
                        job_id_to_use = hashlib.sha256(link_str.encode()).hexdigest()[:64]
                        print(f"[INFO] Generated job_id from application_link for: {screening_output.job_title}")
                    else:
                        print(f"[WARNING] Matched job missing job_id and application_link, skipping: {screening_output.job_title}")
                        skipped_count += 1
                        continue
                
                # Find JobPosting UUID using job_id
                job_posting_id = job_id_to_posting_id.get(job_id_to_use)
                
                # Fallback: Try to find by title + company if job_id lookup failed
                if not job_posting_id:
                    for posting in postings:
                        if (posting.title == screening_output.job_title and 
                            posting.company_name == screening_output.job_company):
                            job_posting_id = posting.id
                            print(f"[INFO] Found JobPosting by title+company match for: {screening_output.job_title}")
                            break
                
                if not job_posting_id:
                    print(f"[WARNING] JobPosting not found for job_id: {job_id_to_use} (title: {screening_output.job_title})")
                    skipped_count += 1
                    continue
                
                try:
                    # Create MatchedJob record - aligned with database model
                    matched_job = MatchedJob(
                        id=uuid.uuid4(),
                        job_search_id=job_search_id,
                        job_posting_id=job_posting_id,
                        is_match=screening_output.is_match,
                        reason=screening_output.reason,
                        job_description_summary=screening_output.job_description,
                        application_link=screening_output.application_link,
                    )
                    matched_job_repo.create(matched_job)
                    saved_count += 1
                except Exception as e:
                    job_id_display = job_id_to_use[:50] + "..." if job_id_to_use and len(job_id_to_use) > 50 else (job_id_to_use or "N/A")
                    print(f"[WARNING] Failed to save matched job {job_id_display}: {e}")
                    skipped_count += 1
            
            print(f"[DATABASE] Saved {saved_count}/{len(matched_results)} matched jobs")
            if skipped_count > 0:
                print(f"[DATABASE] Skipped {skipped_count} matched jobs")
            
            # Update JobSearch statistics
            job_search_repo = GenericRepository(session, JobSearch)
            job_search = job_search_repo.get(str(job_search_id))
            if job_search:
                job_search.jobs_screened = len(all_screening_results)
                job_search.matches_found = len(matched_results)
                job_search_repo.update(job_search)
            
        except Exception as e:
            print(f"[ERROR] Database save failed: {e}")
            import traceback
            traceback.print_exc()
            session.rollback()
            raise e
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass


def create_screening_agent(
    model: str = "google-gla:gemini-2.5-flash",
) -> JobScreeningAgent:
    """Factory function to create a job screening agent.

    Args:
        model: The AI model to use for job matching

    Returns:
        JobScreeningAgent instance
    """
    return JobScreeningAgent(model=model)
