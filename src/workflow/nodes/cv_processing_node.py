"""CV processing node for extracting and structuring user profile from PDF documents."""

import tempfile
import uuid
import logging
from typing import Optional, List

import requests

from pydantic_ai import Agent
from pydantic import BaseModel, Field

from src.workflow.base_node import BaseNode
from src.workflow.profiling_context import ProfilingWorkflowContext
from src.profiling.pdf_parser import PDFParser
from src.database import GenericRepository, UserProfile
from src.config import (
    DOWNLOAD_TIMEOUT_SEC,
    DOWNLOAD_MAX_BYTES,
    DEFAULT_NUM_JOB_TITLES,
)
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ProfilingOutput(BaseModel):
    """Output model for user profile extraction."""

    name: str = Field(description="User's full name extracted from the documents")

    email: str = Field(description="User's email address extracted from the documents")

    profile: str = Field(
        description="A detailed and comprehensive profile of the user including "
        "education, work experience, skills, and other relevant information."
    )

    references: Optional[dict] = Field(
        default=None,
        description="Optional references like LinkedIn URL, portfolio URL, etc.",
    )

    suggested_job_titles: List[str] = Field(
        default_factory=list,
        description="List of relevant job titles based on the user's profile, "
        "skills, experience, and background. Titles should be specific "
        "and industry-standard (e.g., 'Full-Stack Developer', 'Data Scientist', "
        "'Registered Chinese Medical Practitioner').",
    )


class CVProcessingNode(BaseNode):
    """Node for processing CV/PDF documents and building structured user profile."""

    def __init__(
        self,
        model: str = "google-gla:gemini-2.5-flash",
        num_job_titles: int = DEFAULT_NUM_JOB_TITLES,
    ):
        """Initialize the CV processing node.

        Args:
            model: AI model to use for profile extraction
            num_job_titles: Number of job titles to suggest (default: 3)
        """
        super().__init__()
        self.model = model
        self.num_job_titles = num_job_titles
        self.parser = PDFParser()

    def _validate_context(self, context: ProfilingWorkflowContext) -> bool:
        """Validate required context fields for CV processing.

        Args:
            context: The workflow context

        Returns:
            True if valid, False otherwise
        """
        if not context.cv_urls or len(context.cv_urls) == 0:
            context.add_error("At least one CV URL is required for CV processing")
            return False
        return True

    def _build_profile_from_urls(self, urls: list[str]) -> str:
        """Download PDFs from URLs and extract combined text.

        Args:
            urls: List of URLs to CV/PDF documents

        Returns:
            Combined extracted text from all PDFs
        """
        all_text = []

        for url in urls:
            url = (url or "").strip()
            if not url:
                continue
            if not (url.startswith("http://") or url.startswith("https://")):
                self.logger.warning(f"Skipping invalid URL scheme: {url[:50]}...")
                continue

            try:
                resp = requests.get(
                    url,
                    timeout=DOWNLOAD_TIMEOUT_SEC,
                    stream=True,
                )
                resp.raise_for_status()

                content_length = resp.headers.get("Content-Length")
                if content_length and int(content_length) > DOWNLOAD_MAX_BYTES:
                    self.logger.warning(
                        f"URL exceeds max size ({DOWNLOAD_MAX_BYTES} bytes): {url[:50]}..."
                    )
                    continue

                accumulated = 0
                chunks = []
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        accumulated += len(chunk)
                        if accumulated > DOWNLOAD_MAX_BYTES:
                            self.logger.warning(
                                f"URL exceeded max size while streaming: {url[:50]}..."
                            )
                            break
                        chunks.append(chunk)

                content = b"".join(chunks)
                if not content:
                    self.logger.warning(f"Empty response from URL: {url[:50]}...")
                    continue

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                    tmp.write(content)
                    tmp.flush()
                    self.logger.info(f"Parsing PDF from URL: {url[:60]}...")
                    text = self.parser.parse(tmp.name)
                    label = url.split("/")[-1] or "document"
                    all_text.append(f"--- Content from {label} ---\n{text}")

            except requests.RequestException as e:
                self.logger.error(f"Failed to download {url[:50]}...: {e}")
            except Exception as e:
                self.logger.error(f"Failed to parse PDF from {url[:50]}...: {e}")

        return "\n\n".join(all_text)

    def _persist_data(self, context: ProfilingWorkflowContext, session) -> None:
        """Save user profile to database.

        Args:
            context: The workflow context with profile information
            session: Database session
        """
        if not context.name or not context.email or not context.user_profile:
            self.logger.warning("Missing profile information, cannot persist")
            return

        try:
            source_urls = list(context.cv_urls) if context.cv_urls else []

            profile_repo = GenericRepository(session, UserProfile)

            # Check if profile with this name and email already exists
            existing = profile_repo.find_one(name=context.name, email=context.email)
            if existing:
                # Update existing profile
                existing.profile_text = context.user_profile
                existing.location = context.location
                if source_urls:
                    existing.source_pdfs = source_urls
                if context.references:
                    existing.references = context.references
                existing.suggested_job_titles = context.suggested_job_titles or []
                profile_repo.update(existing)
                context.profile_id = existing.id
                self.logger.info(f"Updated existing user profile (ID: {existing.id})")
            else:
                # Create new profile
                new_profile = UserProfile(
                    id=uuid.uuid4(),
                    name=context.name,
                    email=context.email,
                    location=context.location,
                    profile_text=context.user_profile,
                    source_pdfs=source_urls,
                    references=context.references,
                    suggested_job_titles=context.suggested_job_titles or [],
                )
                profile_repo.create(new_profile)
                context.profile_id = new_profile.id
                self.logger.info(f"Saved new user profile (ID: {new_profile.id})")
        except Exception as e:
            self.logger.error(f"Failed to save profile to database: {e}")
            raise

    async def run(self, context: ProfilingWorkflowContext) -> ProfilingWorkflowContext:
        """Process CV/PDF documents from URLs and build structured user profile.

        Args:
            context: The workflow context with user input and CV URLs

        Returns:
            Updated context with profile information
        """
        self.logger.info("Starting CV processing")

        # Validate context
        if not self._validate_context(context):
            self.logger.error("Context validation failed")
            return context

        # Extract text from PDFs at URLs
        self.logger.info("Extracting text from CV URLs...")
        raw_text = self._build_profile_from_urls(context.cv_urls)
        context.raw_cv_text = raw_text

        if not raw_text.strip():
            context.add_error(
                "No PDF content could be extracted from the provided URLs. "
                "Check that URLs are valid and point to PDF files."
            )
            self.logger.error("No PDF content extracted from URLs")
            return context

        # Use AI agent to structure the profile
        self.logger.info("Building structured profile using AI...")

        profiling_agent = Agent(model=self.model, output_type=ProfilingOutput)

        # Combine user-provided basic info with CV content
        basic_info_section = ""
        if context.basic_info:
            basic_info_section = (
                f"\n\nAdditional Information Provided by User:\n{context.basic_info}"
            )

        prompt = f"""Extract and structure a comprehensive user profile from the following documents.

IMPORTANT: Extract the following information:
1. Full name of the person (use: {context.name} if found in documents, otherwise extract)
2. Email address (use: {context.email} if found in documents, otherwise extract)
3. Any references (LinkedIn URL, portfolio URL, GitHub, etc.)
4. Education background
5. Work experience and roles
6. Technical skills and competencies
7. Languages spoken
8. Certifications
9. Any other relevant professional information

Additionally, analyze the user's profile and suggest {self.num_job_titles} relevant job titles 
that match their skills, experience, and background. Consider:
- Their technical skills and technologies
- Their work experience and roles
- Their education and certifications
- Industry standards and common job titles

Documents:
{raw_text}{basic_info_section}

Return a structured response with name, email, references (if any), a detailed profile, and 
suggested_job_titles. Job titles should be specific and industry-standard (e.g., 
'Full-Stack Developer', 'Data Scientist', 'Registered Chinese Medical Practitioner')."""

        result = await profiling_agent.run(prompt)
        output = result.output

        # Update context with profile information
        context.user_profile = output.profile or ""
        context.references = output.references
        context.suggested_job_titles = output.suggested_job_titles or []

        # Use extracted name/email from LLM (prefer user-provided, fallback to LLM)
        if not context.name:
            context.name = output.name
        if not context.email:
            context.email = output.email

        # If profile is empty, add error
        if not context.user_profile:
            context.add_error(
                "Profile was built but is empty. Check PDF URLs and LLM output."
            )
            self.logger.error("Profile is empty after extraction")
            return context

        # Persist to database
        session_gen = self._get_db_session()
        session = next(session_gen)
        try:
            self._persist_data(context, session)
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to persist profile: {e}")
            context.add_error(f"Failed to save profile to database: {e}")
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass

        self.logger.info("CV processing completed")
        return context
