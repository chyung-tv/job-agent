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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database.session import Base

if TYPE_CHECKING:
    from src.workflow.context import WorkflowContext
    from src.discovery.serpapi_models import JobResult
    from src.matcher.matcher import JobScreeningOutput

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
        return cls(
            id=context.job_search_id or uuid.uuid4(),
            query=context.query,
            location=context.location,
            google_domain=context.google_domain,
            hl=context.hl,
            gl=context.gl,
            total_jobs_found=total_jobs_found,
        )


# I think we need to consider how to handle searched job posting either delete duplicated or not storing it at all I can only imagine with each search gets 50 of this the database will explode
class JobPosting(Base):
    """Model representing a single job posting from SerpAPI.

    Stores individual job results from job search queries.
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


class UserProfile(Base):
    """UserProfile model to store the structured user profile.

    Stores user information extracted from PDFs so the profiling step can check
    if a profile exists under the same name and email before calling the LLM.
    """

    __tablename__ = "user_profiles"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the user profile",
    )

    # User identification (used for lookup)
    name = Column(
        String(255),
        nullable=False,
        doc="User's full name extracted from PDFs",
    )

    email = Column(
        String(255),
        nullable=False,
        doc="User's email address extracted from PDFs",
    )

    # Unique constraint on name + email combination
    __table_args__ = (
        UniqueConstraint("name", "email", name="uq_user_profile_name_email"),
    )

    # Profile content
    profile_text = Column(
        Text,
        nullable=False,
        doc="Structured user profile text extracted from PDFs",
    )

    # Source information
    references = Column(
        JSON,
        nullable=True,
        doc="References like file names, URLs, LinkedIn profile, etc.",
    )

    source_pdfs = Column(
        JSON,
        nullable=True,
        doc="List of PDF file paths used to generate this profile",
    )

    # Timestamps
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the profile was created",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the profile was last updated",
    )

    # Usage tracking
    last_used_at = Column(
        DateTime,
        nullable=True,
        doc="Timestamp when the profile was last used in a job search",
    )

    @classmethod
    def from_context(
        cls,
        context: "WorkflowContext",
        references: Optional[dict] = None,
        pdf_paths: Optional[list] = None,
    ) -> "UserProfile":
        """Create a UserProfile instance from WorkflowContext.

        Args:
            context: WorkflowContext object containing profile information
            references: Optional references (LinkedIn, portfolio, etc.)
            pdf_paths: Optional list of PDF file paths (will be converted to strings)

        Returns:
            UserProfile instance

        Raises:
            ValueError: If context doesn't have required profile information
        """
        if (
            not context.user_profile
            or not context.profile_name
            or not context.profile_email
        ):
            raise ValueError(
                "Context must have user_profile, profile_name, and profile_email"
            )

        pdf_paths_str = [str(p) for p in pdf_paths] if pdf_paths else None

        return cls(
            id=uuid.uuid4(),
            name=context.profile_name,
            email=context.profile_email,
            profile_text=context.user_profile,
            references=references,
            source_pdfs=pdf_paths_str,
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


class CoverLetter(Base):
    """CoverLetter model to store fabricated cover letter results.
    
    Stores the topic and complete content of cover letters generated
    for matched jobs. Each matched job can have one cover letter.
    """
    
    __tablename__ = "cover_letters"
    
    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the cover letter",
    )
    
    # Foreign key
    matched_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("matched_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One cover letter per matched job
        doc="Reference to the matched job",
    )
    
    # Cover letter content
    topic = Column(
        JSON,
        nullable=False,
        doc="Cover letter topic and summary (stored as JSON from CoverLetterTopic)",
    )
    
    content = Column(
        JSON,
        nullable=False,
        doc="Complete cover letter content (stored as JSON from CoverLetterContent)",
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when the cover letter was created",
    )
    
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        doc="Timestamp when the cover letter was last updated",
    )
    
    # Relationship
    matched_job = relationship("MatchedJob", backref="cover_letter")


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