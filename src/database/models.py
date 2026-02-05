"""SQLAlchemy database models for job-agent application."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    String,
    Boolean,
    ForeignKey,
    Text,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database.session import Base

if TYPE_CHECKING:
    from src.workflow.base_context import (
        JobSearchWorkflowContext as WorkflowContext,
    )  # Alias for backward compatibility
    from src.discovery.serpapi_models import JobResult
    from src.matcher.matcher import JobScreeningOutput


class User(Base):
    """User table: Better Auth auth columns + job-agent profile columns.

    Table name 'user' and camelCase column names (emailVerified, createdAt, updatedAt)
    match Better Auth defaults for prismaAdapter. Profile columns are nullable until
    the user runs the profiling workflow.
    """

    __tablename__ = "user"

    # Better Auth uses string identifiers for user id (not necessarily UUID; may be nanoid or other).
    id = Column(
        String(255),
        primary_key=True,
        doc="Unique identifier (Better Auth; string, not UUID)",
    )
    name = Column(String(255), nullable=False, default="", doc="Display name")
    email = Column(String(255), nullable=False, default="", doc="Email address")
    emailVerified = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether email is verified (Better Auth)",
    )
    image = Column(String(500), nullable=True, doc="Profile image URL")
    createdAt = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        doc="Created timestamp (Better Auth)",
    )
    updatedAt = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        doc="Updated timestamp (Better Auth)",
    )
    # Beta access control
    hasAccess = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Beta access control - manually toggled by admin",
    )
    # Profile columns (nullable)
    location = Column(String(255), nullable=True, doc="Preferred job search location")
    profile_text = Column(Text, nullable=True, doc="Structured profile text from PDFs")
    suggested_job_titles = Column(JSON, nullable=True, doc="AI-suggested job titles")
    source_pdfs = Column(JSON, nullable=True, doc="Source PDF paths")
    references = Column(
        JSON, nullable=True, doc="References (LinkedIn, portfolio, etc.)"
    )
    last_used_at = Column(DateTime, nullable=True, doc="Last used in a job search")


class Run(Base):
    """Model representing a run of the application workflow.

    Tracks the complete workflow execution from job search through matching,
    research, fabrication, and delivery. Used for orchestration and completion tracking.
    """

    __tablename__ = "runs"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the run",
    )

    # Foreign keys
    job_search_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_searches.id", ondelete="CASCADE"),
        nullable=True,  # Nullable initially for migration
        doc="Reference to the job search workflow",
    )
    # String to match User.id (Better Auth); not necessarily a UUID.
    user_id = Column(
        String(255),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        doc="User owner for this run (used to send delivery email)",
    )

    # Celery task id (for linking to Flower / task status)
    task_id = Column(
        String(255),
        nullable=True,
        doc="Celery task id for this run",
    )

    # Status tracking
    status = Column(
        String(255),
        nullable=False,
        default="pending",
        doc="Run status: pending, processing, completed, failed",
    )
    error_message = Column(
        Text,
        nullable=True,
        doc="Error message if run failed",
    )

    # Completion counters
    total_matched_jobs = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Total number of matched jobs in this run",
    )
    research_completed_count = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of matched jobs with completed research",
    )
    fabrication_completed_count = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of matched jobs with completed fabrication",
    )
    research_failed_count = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of matched jobs with failed research",
    )
    fabrication_failed_count = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of matched jobs with failed fabrication",
    )

    # Completion timestamps
    completed_at = Column(
        DateTime,
        nullable=True,
        doc="Timestamp when the run completed (all matched jobs finished)",
    )

    # Delivery tracking
    delivery_triggered = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether delivery has been triggered for this run",
    )
    delivery_triggered_at = Column(
        DateTime,
        nullable=True,
        doc="Timestamp when delivery was triggered",
    )

    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the run was created",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the run was last updated",
    )

    # Relationships
    job_search = relationship("JobSearch", backref="runs")
    user = relationship("User", backref="runs", foreign_keys=[user_id])


class JobSearch(Base):
    """Model representing a job search workflow run.

    Stores metadata about a complete job search workflow execution,
    including search parameters and summary statistics.
    """

    __tablename__ = "job_searches"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the job search workflow",
    )

    # Search parameters
    query = Column(
        String(255),
        nullable=False,
        doc="Job search query (e.g., 'software engineer', 'ai developer')",
    )
    location = Column(
        String(255),
        nullable=False,
        doc="Location for the search (e.g., 'Hong Kong')",
    )
    google_domain = Column(
        String(50),
        default="google.com",
        doc="Google domain used for search",
    )
    hl = Column(
        String(10),
        default="en",
        doc="Language code (e.g., 'en')",
    )
    gl = Column(
        String(10),
        default="us",
        doc="Country code (e.g., 'us')",
    )

    # String to match User.id (Better Auth); not necessarily a UUID.
    user_id = Column(
        String(255),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        doc="User who owns this job search",
    )

    # Results summary
    total_jobs_found = Column(
        Integer,
        default=0,
        doc="Total number of jobs found in the search",
    )
    jobs_screened = Column(
        Integer,
        default=0,
        doc="Number of jobs that were screened",
    )
    matches_found = Column(
        Integer,
        default=0,
        doc="Number of jobs that matched the user profile",
    )

    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the search was created",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the search was last updated",
    )

    # Relationships
    user = relationship("User", backref="job_searches", foreign_keys=[user_id])
    job_postings = relationship(
        "JobPosting", back_populates="job_search", cascade="all, delete-orphan"
    )
    matched_jobs = relationship(
        "MatchedJob", back_populates="job_search", cascade="all, delete-orphan"
    )

    @classmethod
    def from_context(
        cls, context: "WorkflowContext", total_jobs_found: int = 0
    ) -> "JobSearch":
        """Create a JobSearch instance from WorkflowContext.

        Args:
            context: WorkflowContext object containing search parameters
            total_jobs_found: Total number of jobs found (default: 0)

        Returns:
            JobSearch instance
        """
        user_id = getattr(context, "user_id", None)
        return cls(
            id=context.job_search_id or uuid.uuid4(),
            query=context.query,
            location=context.location,
            google_domain=context.google_domain,
            hl=context.hl,
            gl=context.gl,
            total_jobs_found=total_jobs_found,
            user_id=str(user_id) if user_id else None,
        )


# I think we need to consider how to handle searched job posting either delete duplicated or not storing it at all I can only imagine with each search gets 50 of this the database will explode
class JobPosting(Base):
    """Model representing a single job posting from SerpAPI.

    Stores individual job results from job search queries. Company research
    is associated via the company_research relationship (one-to-one per posting).
    """

    __tablename__ = "job_postings"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the job posting",
    )

    # Foreign key
    job_search_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_searches.id", ondelete="CASCADE"),
        nullable=False,
        doc="Reference to the job search that found this posting",
    )

    # Job details from SerpAPI
    job_id = Column(
        Text,
        nullable=True,
        doc="Job ID from SerpAPI (base64-encoded, can be very long)",
    )
    title = Column(
        String(500),
        nullable=True,
        doc="Job title",
    )
    company_name = Column(
        String(255),
        nullable=True,
        doc="Company name",
    )
    location = Column(
        String(255),
        nullable=True,
        doc="Job location",
    )
    via = Column(
        String(255),
        nullable=True,
        doc="Platform where job was found (e.g., 'LinkedIn', 'Indeed')",
    )
    share_link = Column(
        String(1000),
        nullable=True,
        doc="Share link for the job posting",
    )
    description = Column(
        Text,
        nullable=True,
        doc="Full job description",
    )

    # JSON fields for complex data
    extensions = Column(
        JSON,
        nullable=True,
        doc="List of extensions/tags from SerpAPI",
    )
    detected_extensions = Column(
        JSON,
        nullable=True,
        doc="Detected extensions (benefits, schedule, etc.)",
    )
    job_highlights = Column(
        JSON,
        nullable=True,
        doc="Job highlights/key points",
    )
    apply_options = Column(
        JSON,
        nullable=True,
        doc="Available application options",
    )

    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the posting was created",
    )

    # Relationships
    job_search = relationship("JobSearch", back_populates="job_postings")
    matched_job = relationship(
        "MatchedJob", back_populates="job_posting", uselist=False
    )

    @classmethod
    def from_job_result(
        cls, job_result: "JobResult", job_search_id: uuid.UUID
    ) -> "JobPosting":
        """Create a JobPosting instance from JobResult.

        Args:
            job_result: JobResult object from SerpAPI
            job_search_id: UUID of the associated JobSearch

        Returns:
            JobPosting instance
        """
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

        return cls(
            id=uuid.uuid4(),
            job_search_id=job_search_id,
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


class MatchedJob(Base):
    """Model representing a job that matched the user profile.

    Stores results from the AI screening agent, including match status
    and reasoning.
    """

    __tablename__ = "matched_jobs"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the matched job record",
    )

    # Foreign keys
    job_search_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_searches.id", ondelete="CASCADE"),
        nullable=False,
        doc="Reference to the job search workflow",
    )
    job_posting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        doc="Reference to the job posting",
    )
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=True,  # Nullable initially for migration
        doc="Reference to the run that processes this matched job",
    )
    # String to match User.id (Better Auth); not necessarily a UUID.
    user_id = Column(
        String(255),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        doc="User who owns this matched job (denormalized for scoping)",
    )

    # Match details from AI screening
    is_match = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether the job matches the user profile",
    )
    reason = Column(
        Text,
        nullable=False,
        doc="Detailed explanation for why it matches or doesn't match",
    )
    job_description_summary = Column(
        Text,
        nullable=True,
        doc="Summary of the job description (from AI agent)",
    )

    # Application link
    application_link = Column(
        JSON,
        nullable=True,
        doc="Application link with 'via' and 'link' keys",
    )

    # Research status tracking
    research_status = Column(
        String(50),
        nullable=False,
        default="pending",
        doc="Research status: pending, processing, completed, failed",
    )
    research_attempts = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of research attempts made",
    )
    research_error = Column(
        Text,
        nullable=True,
        doc="Error message if research failed",
    )
    research_completed_at = Column(
        DateTime,
        nullable=True,
        doc="Timestamp when research was completed",
    )

    # Fabrication status tracking
    fabrication_status = Column(
        String(50),
        nullable=False,
        default="pending",
        doc="Fabrication status: pending, processing, completed, failed",
    )
    fabrication_attempts = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of fabrication attempts made",
    )
    fabrication_error = Column(
        Text,
        nullable=True,
        doc="Error message if fabrication failed",
    )
    fabrication_completed_at = Column(
        DateTime,
        nullable=True,
        doc="Timestamp when fabrication was completed",
    )

    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the match was created",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the match was last updated",
    )

    # Relationships
    user = relationship("User", backref="matched_jobs", foreign_keys=[user_id])
    job_search = relationship("JobSearch", back_populates="matched_jobs")
    job_posting = relationship("JobPosting", back_populates="matched_job")
    run = relationship("Run", backref="matched_jobs")

    @classmethod
    def from_screening_output(
        cls,
        output: "JobScreeningOutput",
        job_search_id: uuid.UUID,
        job_posting_id: uuid.UUID,
    ) -> "MatchedJob":
        """Create a MatchedJob instance from JobScreeningOutput.

        Args:
            output: JobScreeningOutput object from screening agent
            job_search_id: UUID of the associated JobSearch
            job_posting_id: UUID of the associated JobPosting

        Returns:
            MatchedJob instance
        """
        return cls(
            id=uuid.uuid4(),
            job_search_id=job_search_id,
            job_posting_id=job_posting_id,
            is_match=output.is_match,
            reason=output.reason,
            job_description_summary=output.job_description,
            application_link=output.application_link,
        )


class CompanyResearch(Base):
    """CompanyResearch model to store the research results for a company.

    This model stores comprehensive research about a company for a specific job posting.
    The research results contain information that can be cross-referenced with user profiles
    and used to fabricate tailored application materials.
    """

    __tablename__ = "company_research"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the company research",
    )

    # Company and job reference
    company_name = Column(
        String(255),
        nullable=False,
        doc="Company name (denormalized for quick access)",
    )

    job_posting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One research per job posting
        doc="Reference to the job posting",
    )

    # Research content
    research_results = Column(
        Text,
        nullable=False,
        doc="Synthesized research results about the company, team, culture, and expectations",
    )

    citations = Column(
        JSON,
        nullable=True,
        doc="List of citations/sources used in the research (stored as JSON array)",
    )

    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when the research was created",
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        doc="Timestamp when the research was last updated",
    )

    # Relationship
    job_posting = relationship("JobPosting", backref="company_research")


class Artifact(Base):
    """Unified model to store fabricated application materials for matched jobs.

    Stores both cover letter (JSON for Nylas) and CV (PDF URL) in a single row per matched job.
    """

    __tablename__ = "artifacts"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the artifact",
    )

    # Foreign key
    matched_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("matched_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One artifact record per matched job
        doc="Reference to the matched job",
    )

    # Cover letter data (JSON object passed to Nylas)
    cover_letter = Column(
        JSON,
        nullable=True,
        doc="Cover letter data as JSON (topic + content) - ready to pass to Nylas",
    )

    # CV data (contains PDF URL)
    cv = Column(
        JSON,
        nullable=True,
        doc="CV data containing PDF URL: {'pdf_url': 'https://...'}",
    )

    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when the artifact was created",
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        doc="Timestamp when the artifact was last updated",
    )

    # Relationship
    matched_job = relationship("MatchedJob", backref="artifact", uselist=False)


# Better Auth tables (singular names, camelCase columns per Better Auth schema)
class Session(Base):
    __tablename__ = "session"

    id = Column(String(255), primary_key=True, doc="Session ID (Better Auth)")
    userId = Column(
        String(255),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        doc="User ID (Better Auth)",
    )
    token = Column(String(255), nullable=False, doc="Session token")
    expiresAt = Column(DateTime, nullable=False, doc="Expiration (Better Auth)")
    ipAddress = Column(String(255), nullable=True, doc="IP address (Better Auth)")
    userAgent = Column(String(500), nullable=True, doc="User agent (Better Auth)")
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    user = relationship("User", backref="sessions")


class Account(Base):
    __tablename__ = "account"

    id = Column(String(255), primary_key=True, doc="Account ID (Better Auth)")
    userId = Column(
        String(255),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        doc="User ID (Better Auth)",
    )
    accountId = Column(String(255), nullable=False, doc="Provider account ID")
    providerId = Column(String(255), nullable=False, doc="Provider ID")
    accessToken = Column(Text, nullable=True)
    refreshToken = Column(Text, nullable=True)
    accessTokenExpiresAt = Column(DateTime, nullable=True)
    refreshTokenExpiresAt = Column(DateTime, nullable=True)
    scope = Column(String(255), nullable=True)
    idToken = Column(Text, nullable=True)
    password = Column(String(255), nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    user = relationship("User", backref="accounts")


class Verification(Base):
    __tablename__ = "verification"

    id = Column(String(255), primary_key=True, doc="Verification ID (Better Auth)")
    identifier = Column(String(255), nullable=False, doc="Identifier to verify")
    value = Column(String(255), nullable=False, doc="Value to verify")
    expiresAt = Column(DateTime, nullable=False, doc="Expiration")
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
