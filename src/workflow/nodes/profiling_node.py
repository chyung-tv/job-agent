"""Profiling node for extracting and building user profile from PDF documents."""

from pathlib import Path
from typing import Optional
import re
import uuid
import logging
from datetime import datetime

from pydantic_ai import Agent
from pydantic import BaseModel, Field

from src.workflow.base_node import BaseNode
from src.workflow.base_context import JobSearchWorkflowContext
from src.profiling.pdf_parser import PDFParser
from src.database import db_session, GenericRepository, UserProfile
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ProfilingOutput(BaseModel):
    """Output model for user profile extraction."""
    
    name: str = Field(
        description="User's full name extracted from the documents"
    )
    
    email: str = Field(
        description="User's email address extracted from the documents"
    )
    
    profile: str = Field(
        description="A detailed and comprehensive profile of the user including "
        "education, work experience, skills, and other relevant information."
    )
    
    references: Optional[dict] = Field(
        default=None,
        description="Optional references like LinkedIn URL, portfolio URL, etc."
    )


class ProfilingNode(BaseNode):
    """Node for building user profile from PDF documents."""
    
    def __init__(self, model: str = "google-gla:gemini-2.5-flash", use_cache: bool = True):
        """Initialize the profiling node.
        
        Args:
            model: AI model to use for profile extraction
            use_cache: Whether to use cached profile from database
        """
        super().__init__()
        self.model = model
        self.use_cache = use_cache
        self.parser = PDFParser()
    
    def _validate_context(self, context: JobSearchWorkflowContext) -> bool:
        """Validate required context fields for profiling.
        
        Args:
            context: The workflow context
            
        Returns:
            True if valid, False otherwise
        """
        if not context.pdf_paths and not context.data_dir:
            context.add_error("Either pdf_paths or data_dir is required for profiling step")
            return False
        return True
    
    def _extract_name_email_from_text(self, raw_text: str) -> tuple[Optional[str], Optional[str]]:
        """Extract name and email from raw PDF text using simple patterns.
        
        Args:
            raw_text: Raw text extracted from PDFs
            
        Returns:
            Tuple of (name, email) if found, (None, None) otherwise
        """
        # Try to extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, raw_text)
        email = emails[0] if emails else None
        
        # Try to extract name (look for common patterns at the beginning)
        name = None
        lines = raw_text.split('\n')[:10]  # Check first 10 lines
        for line in lines:
            line = line.strip()
            # Look for lines that might be names (2-4 words, title case)
            if 2 <= len(line.split()) <= 4 and line[0].isupper():
                # Skip if it looks like a header or contains common non-name words
                skip_words = ['resume', 'cv', 'curriculum', 'vitae', 'linkedin', 'email', 'phone']
                if not any(word.lower() in line.lower() for word in skip_words):
                    name = line
                    break
        
        return name, email
    
    def _build_profile_from_pdfs(self, pdf_paths: list[Path]) -> str:
        """Extract and combine text from multiple PDF documents.
        
        Args:
            pdf_paths: List of paths to PDF files to parse
            
        Returns:
            Combined extracted text from all PDFs
        """
        all_text = []
        
        for pdf_path in pdf_paths:
            if not pdf_path.exists():
                self.logger.warning(f"File not found: {pdf_path.name}, skipping...")
                continue
            
            self.logger.info(f"Parsing {pdf_path.name}...")
            try:
                text = self.parser.parse(pdf_path)
                all_text.append(f"--- Content from {pdf_path.name} ---\n{text}")
            except Exception as e:
                self.logger.error(f"Failed to parse {pdf_path.name}: {e}")
        
        return "\n\n".join(all_text)
    
    def _load_data(self, context: JobSearchWorkflowContext, session) -> None:
        """Load existing user profile from database if available.
        
        Args:
            context: The workflow context
            session: Database session
        """
        # This will be called after we extract name/email from PDFs
        # For now, we'll do the loading in run() method after extraction
        pass
    
    def _load_profile_from_db(self, name: str, email: str, session) -> Optional[str]:
        """Load user profile from database if it exists.
        
        Args:
            name: User's name
            email: User's email
            session: Database session
            
        Returns:
            Profile text if found, None otherwise
        """
        if not name or not email:
            return None
        
        try:
            profile_repo = GenericRepository(session, UserProfile)
            profile = profile_repo.find_one(name=name, email=email)
            if profile:
                self.logger.info(f"Found cached user profile for {name} ({email})")
                # Update last_used_at
                profile.last_used_at = datetime.utcnow()
                profile_repo.update(profile)
                return profile.profile_text
        except Exception as e:
            self.logger.warning(f"Failed to load profile from database: {e}")
        
        return None
    
    def _persist_data(self, context: JobSearchWorkflowContext, session) -> None:
        """Save user profile to database.
        
        Args:
            context: The workflow context with profile information
            session: Database session
        """
        if not context.profile_name or not context.profile_email or not context.user_profile:
            self.logger.warning("Missing profile information, cannot persist")
            return
        
        try:
            pdf_paths_str = [str(p) for p in (context.pdf_paths or [])]
            
            profile_repo = GenericRepository(session, UserProfile)
            
            # Check if profile with this name and email already exists
            existing = profile_repo.find_one(name=context.profile_name, email=context.profile_email)
            if existing:
                # Update existing profile
                existing.profile_text = context.user_profile
                # Extract references from context if available (would need to be added to context)
                # For now, just update the profile text
                if pdf_paths_str:
                    existing.source_pdfs = pdf_paths_str
                profile_repo.update(existing)
                self.logger.info(f"Updated existing user profile (ID: {existing.id})")
            else:
                # Create new profile
                new_profile = UserProfile(
                    id=uuid.uuid4(),
                    name=context.profile_name,
                    email=context.profile_email,
                    profile_text=context.user_profile,
                    source_pdfs=pdf_paths_str,
                )
                profile_repo.create(new_profile)
                self.logger.info(f"Saved new user profile (ID: {new_profile.id})")
        except Exception as e:
            self.logger.error(f"Failed to save profile to database: {e}")
            raise
    
    async def run(self, context: JobSearchWorkflowContext) -> JobSearchWorkflowContext:
        """Build user profile from PDF documents.
        
        Args:
            context: The workflow context with pdf_paths and/or data_dir
            
        Returns:
            Updated context with profile information
        """
        self.logger.info("Starting profiling node")
        
        # Validate context
        if not self._validate_context(context):
            self.logger.error("Context validation failed")
            return context
        
        # Set default data_dir if not provided
        if context.data_dir is None and context.pdf_paths is None:
            context.data_dir = Path(__file__).parent.parent.parent.parent / "data"
        
        # Determine which PDFs to parse
        pdf_paths = context.pdf_paths
        if pdf_paths is None:
            data_dir = context.data_dir
            # Look for common PDF files
            common_files = ["linkdeln.pdf", "linkedin.pdf", "CV_YungCH.pdf", "cv.pdf", "resume.pdf"]
            pdf_paths = [data_dir / f for f in common_files if (data_dir / f).exists()]
        
        if not pdf_paths:
            context.add_error("No PDF files found to parse. Please provide pdf_paths or ensure PDFs exist in data directory.")
            self.logger.error("No PDF files found to parse")
            return context
        
        # Extract text from PDFs
        self.logger.info("Extracting text from PDF documents...")
        raw_text = self._build_profile_from_pdfs(pdf_paths)
        
        # Try to extract name and email from raw text (for cache lookup)
        name, email = self._extract_name_email_from_text(raw_text)
        
        # Try to load from database cache
        was_cached = False
        profile_text = None
        if self.use_cache and name and email:
            session_gen = self._get_db_session()
            session = next(session_gen)
            try:
                cached_profile = self._load_profile_from_db(name, email, session)
                if cached_profile:
                    profile_text = cached_profile
                    was_cached = True
                    self.logger.info("Using cached profile from database")
            finally:
                try:
                    next(session_gen, None)
                except StopIteration:
                    pass
        
        # If not cached, use AI agent to structure the profile
        if not profile_text:
            self.logger.info("Building structured profile using AI...")
            
            profiling_agent = Agent(model=self.model, output_type=ProfilingOutput)
            
            prompt = f"""Extract and structure a comprehensive user profile from the following documents.

IMPORTANT: Extract the following information:
1. Full name of the person
2. Email address
3. Any references (LinkedIn URL, portfolio URL, GitHub, etc.)
4. Education background
5. Work experience and roles
6. Technical skills and competencies
7. Languages spoken
8. Certifications
9. Any other relevant professional information

Documents:
{raw_text}

Return a structured response with name, email, references (if any), and a detailed profile."""
            
            # Use async run() instead of run_sync()
            result = await profiling_agent.run(prompt)
            output = result.output
            
            # Use extracted name/email from LLM
            name = output.name
            email = output.email
            profile_text = output.profile
            # references = output.references  # Could store this in context if needed
        
        # Update context with profile information
        context.user_profile = profile_text or ""
        context.profile_was_cached = was_cached
        context.profile_name = name
        context.profile_email = email
        
        # If profile is empty, add error
        if not context.user_profile:
            context.add_error("Profile was built but is empty. Check PDF files and LLM output.")
            self.logger.error("Profile is empty after extraction")
        
        # Persist to database (only if not cached, since cached profiles are already in DB)
        if not was_cached and profile_text:
            session_gen = self._get_db_session()
            session = next(session_gen)
            try:
                self._persist_data(context, session)
            except Exception as e:
                self.logger.error(f"Failed to persist profile: {e}")
                context.add_error(f"Failed to save profile to database: {e}")
            finally:
                try:
                    next(session_gen, None)
                except StopIteration:
                    pass
        
        self.logger.info("Profiling node completed")
        return context
