"""Generic repository pattern for database operations."""

import uuid
from typing import Generic, TypeVar, Type, List, Optional, Union, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from src.workflow.base_context import (
        JobSearchWorkflowContext as WorkflowContext,
    )  # Alias for backward compatibility
    from src.discovery.serpapi_models import JobResult
    from src.matcher.matcher import JobScreeningOutput

T = TypeVar("T")


class GenericRepository(Generic[T]):
    """Generic repository for database operations.

    Provides common CRUD operations for any SQLAlchemy model.

    Example:
        ```python
        session = next(db_session())
        job_repo = GenericRepository(session, JobSearch)

        # Create
        new_job = JobSearch(...)
        job_repo.create(new_job)

        # Read
        job = job_repo.get(job_id)
        all_jobs = job_repo.get_all()

        # Update
        job.field = "new_value"
        job_repo.update(job)

        # Delete
        job_repo.delete(job_id)
        ```
    """

    def __init__(self, session: Session, model: Type[T]):
        """Initialize repository.

        Args:
            session: SQLAlchemy session instance
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model

    def create(self, obj: T) -> T:
        """Create a new record.

        Args:
            obj: Model instance to create

        Returns:
            Created model instance with ID populated
        """
        self.session.add(obj)  # Stage the object
        self.session.commit()  # Save to database
        self.session.refresh(obj)  # Refresh to get database-generated values
        return obj

    def get(self, id: Union[str, UUID]) -> Optional[T]:
        """Get a record by ID.

        Args:
            id: Primary key ID (can be string or UUID)

        Returns:
            Model instance or None if not found
        """
        return self.session.query(self.model).filter(self.model.id == id).first()

    def get_all(self) -> List[T]:
        """Get all records.

        Returns:
            List of all model instances
        """
        return self.session.query(self.model).all()

    def update(self, obj: T) -> T:
        """Update an existing record.

        Args:
            obj: Model instance with updated values

        Returns:
            Updated model instance
        """
        self.session.merge(obj)  # Merge changes
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def delete(self, id: str) -> None:
        """Delete a record by ID.

        Args:
            id: Primary key ID
        """
        obj = self.get(id)
        if obj:
            self.session.delete(obj)
            self.session.commit()

    def get_latest(self, n: int = 1) -> List[T]:
        """Get the latest N records ordered by ID.

        Args:
            n: Number of records to retrieve

        Returns:
            List of latest model instances
        """
        return (
            self.session.query(self.model).order_by(desc(self.model.id)).limit(n).all()
        )

    def count(self) -> int:
        """Count all records.

        Returns:
            Total number of records
        """
        return self.session.query(self.model).count()

    def filter_by(self, **kwargs) -> List[T]:
        """Filter records by keyword arguments.

        Args:
            **kwargs: Field name and value pairs to filter by

        Returns:
            List of matching model instances

        Example:
            ```python
            jobs = repo.filter_by(location="Hong Kong", is_match=True)
            ```
        """
        return self.session.query(self.model).filter_by(**kwargs).all()

    def find_one(self, **kwargs) -> Optional[T]:
        """Find a single record matching the criteria.

        Args:
            **kwargs: Field name and value pairs to filter by

        Returns:
            First matching model instance or None
        """
        return self.session.query(self.model).filter_by(**kwargs).first()


# Context-aware database helper functions


def save_job_search_from_context(
    context: "WorkflowContext",
    session: Session,
    total_jobs_found: int = 0,
) -> uuid.UUID:
    """Save or update JobSearch from WorkflowContext.

    Args:
        context: WorkflowContext object containing search parameters
        session: Database session
        total_jobs_found: Total number of jobs found

    Returns:
        JobSearch UUID
    """
    from src.database.models import JobSearch

    repo = GenericRepository(session, JobSearch)

    if context.job_search_id:
        job_search = repo.get(str(context.job_search_id))
        if not job_search:
            raise ValueError(f"JobSearch with ID {context.job_search_id} not found")
    else:
        job_search = JobSearch.from_context(context, total_jobs_found)
        job_search = repo.create(job_search)
        print(f"[DATABASE] Created JobSearch: {job_search.id}")

    context.job_search_id = job_search.id
    return job_search.id


def save_job_postings_from_context(
    context: "WorkflowContext",
    session: Session,
) -> int:
    """Save job postings from WorkflowContext.

    Args:
        context: WorkflowContext object containing jobs
        session: Database session

    Returns:
        Number of job postings saved
    """
    from src.database.models import JobPosting, JobSearch

    if not context.jobs or not context.job_search_id:
        return 0

    posting_repo = GenericRepository(session, JobPosting)
    saved_count = 0
    failed_count = 0

    for job_result in context.jobs:
        try:
            job_posting = JobPosting.from_job_result(job_result, context.job_search_id)
            posting_repo.create(job_posting)
            saved_count += 1
        except Exception as e:
            failed_count += 1
            job_id_display = (
                job_result.job_id[:50] + "..."
                if job_result.job_id and len(job_result.job_id) > 50
                else (job_result.job_id or "N/A")
            )
            print(f"[WARNING] Failed to save job posting {job_id_display}: {e}")
            try:
                if session.in_transaction():
                    session.rollback()
            except Exception:
                pass
            continue

    if failed_count > 0:
        print(f"[DATABASE] Failed to save {failed_count} job postings")

    print(f"[DATABASE] Saved {saved_count}/{len(context.jobs)} job postings")

    # Update JobSearch total count
    if saved_count > 0:
        search_repo = GenericRepository(session, JobSearch)
        job_search = search_repo.get(str(context.job_search_id))
        if job_search:
            job_search.total_jobs_found = len(context.jobs)
            search_repo.update(job_search)

    return saved_count


def find_job_posting_by_screening_output(
    screening_output: "JobScreeningOutput",
    job_search_id: uuid.UUID,
    session: Session,
) -> Optional[uuid.UUID]:
    """Find JobPosting UUID for a screening output.

    Tries multiple lookup strategies:
    1. By job_id
    2. By title + company_name

    Args:
        screening_output: JobScreeningOutput object
        job_search_id: JobSearch UUID to filter by
        session: Database session

    Returns:
        JobPosting UUID if found, None otherwise
    """
    from src.database.models import JobPosting

    posting_repo = GenericRepository(session, JobPosting)

    # Try by job_id first
    job_id_to_use = screening_output.job_id
    if not job_id_to_use or job_id_to_use.strip() == "":
        # Generate from application_link if available
        if screening_output.application_link and screening_output.application_link.get(
            "link"
        ):
            import hashlib

            link_str = screening_output.application_link["link"]
            job_id_to_use = hashlib.sha256(link_str.encode()).hexdigest()[:64]
        else:
            job_id_to_use = None

    if job_id_to_use:
        posting = posting_repo.find_one(
            job_search_id=job_search_id, job_id=job_id_to_use
        )
        if posting:
            return posting.id

    # Fallback: try by title + company
    if screening_output.job_title and screening_output.job_company:
        posting = posting_repo.find_one(
            job_search_id=job_search_id,
            title=screening_output.job_title,
            company_name=screening_output.job_company,
        )
        if posting:
            return posting.id

    return None


def save_matched_jobs_from_context(
    context: "WorkflowContext",
    session: Session,
) -> int:
    """Save matched jobs from WorkflowContext.

    Args:
        context: WorkflowContext object containing matched_results
        session: Database session

    Returns:
        Number of matched jobs saved
    """
    from src.database.models import MatchedJob

    if not context.matched_results or not context.job_search_id:
        return 0

    matched_repo = GenericRepository(session, MatchedJob)
    saved_count = 0
    skipped_count = 0

    for screening_output in context.matched_results:
        job_posting_id = find_job_posting_by_screening_output(
            screening_output,
            context.job_search_id,
            session,
        )

        if not job_posting_id:
            print(f"[WARNING] JobPosting not found for: {screening_output.job_title}")
            skipped_count += 1
            continue

        try:
            matched_job = MatchedJob.from_screening_output(
                screening_output,
                context.job_search_id,
                job_posting_id,
            )
            matched_repo.create(matched_job)
            saved_count += 1
        except Exception as e:
            print(f"[WARNING] Failed to save matched job: {e}")
            skipped_count += 1

    print(f"[DATABASE] Saved {saved_count}/{len(context.matched_results)} matched jobs")
    if skipped_count > 0:
        print(f"[DATABASE] Skipped {skipped_count} matched jobs")

    return saved_count


def update_job_search_stats_from_context(
    context: "WorkflowContext",
    session: Session,
) -> None:
    """Update JobSearch statistics from WorkflowContext.

    Args:
        context: WorkflowContext object containing statistics
        session: Database session
    """
    from src.database.models import JobSearch

    if not context.job_search_id:
        return

    repo = GenericRepository(session, JobSearch)
    job_search = repo.get(str(context.job_search_id))

    if job_search:
        job_search.jobs_screened = len(context.all_screening_results)
        job_search.matches_found = len(context.matched_results)
        repo.update(job_search)
        print("[DATABASE] Updated job search statistics")


def load_user_profile_from_context(
    context: "WorkflowContext",
    session: Session,
) -> Optional[str]:
    """Load user profile from database using context.

    Args:
        context: WorkflowContext object (will check profile_name and profile_email)
        session: Database session

    Returns:
        Profile text if found, None otherwise
    """
    from src.database.models import UserProfile
    from datetime import datetime

    if not context.profile_name or not context.profile_email:
        return None

    repo = GenericRepository(session, UserProfile)
    profile = repo.find_one(name=context.profile_name, email=context.profile_email)

    if profile:
        print(
            f"[DATABASE] Found cached user profile for {context.profile_name} ({context.profile_email})"
        )
        profile.last_used_at = datetime.utcnow()
        repo.update(profile)
        return profile.profile_text

    return None


def save_user_profile_from_context(
    context: "WorkflowContext",
    session: Session,
    references: Optional[dict] = None,
    pdf_paths: Optional[List] = None,
) -> uuid.UUID:
    """Save user profile from WorkflowContext.

    Args:
        context: WorkflowContext object containing profile information
        session: Database session
        references: Optional references (LinkedIn, portfolio, etc.)
        pdf_paths: Optional list of PDF file paths

    Returns:
        UserProfile UUID
    """
    from src.database.models import UserProfile

    if (
        not context.user_profile
        or not context.profile_name
        or not context.profile_email
    ):
        raise ValueError(
            "Context must have user_profile, profile_name, and profile_email"
        )

    repo = GenericRepository(session, UserProfile)

    # Check if profile exists
    existing = repo.find_one(name=context.profile_name, email=context.profile_email)

    if existing:
        existing.profile_text = context.user_profile
        existing.references = references
        if pdf_paths:
            existing.source_pdfs = [str(p) for p in pdf_paths]
        # Update location if available in context
        if hasattr(context, "location"):
            existing.location = context.location
        # Update suggested_job_titles if available in context
        if hasattr(context, "suggested_job_titles"):
            existing.suggested_job_titles = context.suggested_job_titles or []
        repo.update(existing)
        print(f"[DATABASE] Updated existing user profile (ID: {existing.id})")
        return existing.id
    else:
        new_profile = UserProfile.from_context(context, references, pdf_paths)
        new_profile = repo.create(new_profile)
        print(f"[DATABASE] Saved new user profile (ID: {new_profile.id})")
        return new_profile.id
