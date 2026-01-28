"""CV processing node for extracting and structuring user profile from PDF documents."""

from pathlib import Path
from typing import Optional
import uuid
import logging
from datetime import datetime

from pydantic_ai import Agent
from pydantic import BaseModel, Field

from src.workflow.base_node import BaseNode
from src.workflow.profiling_context import ProfilingWorkflowContext
from src.profiling.pdf_parser import PDFParser
from src.database import GenericRepository, UserProfile
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


class CVProcessingNode(BaseNode):
    """Node for processing CV/PDF documents and building structured user profile."""
    
    def __init__(self, model: str = "google-gla:gemini-2.5-flash"):
        """Initialize the CV processing node.
        
        Args:
            model: AI model to use for profile extraction
        """
        super().__init__()
        self.model = model
        self.parser = PDFParser()
    
    def _validate_context(self, context: ProfilingWorkflowContext) -> bool:
        """Validate required context fields for CV processing.
        
        Args:
            context: The workflow context
            
        Returns:
            True if valid, False otherwise
        """
        if not context.pdf_paths and not context.data_dir:
            context.add_error("Either pdf_paths or data_dir is required for CV processing")
            return False
        return True
    
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
            pdf_paths_str = [str(p) for p in (context.pdf_paths or [])]
            
            profile_repo = GenericRepository(session, UserProfile)
            
            # Check if profile with this name and email already exists
            existing = profile_repo.find_one(name=context.name, email=context.email)
            if existing:
                # Update existing profile
                existing.profile_text = context.user_profile
                if pdf_paths_str:
                    existing.source_pdfs = pdf_paths_str
                if context.references:
                    existing.references = context.references
                profile_repo.update(existing)
                context.profile_id = existing.id
                self.logger.info(f"Updated existing user profile (ID: {existing.id})")
            else:
                # Create new profile
                new_profile = UserProfile(
                    id=uuid.uuid4(),
                    name=context.name,
                    email=context.email,
                    profile_text=context.user_profile,
                    source_pdfs=pdf_paths_str,
                    references=context.references,
                )
                profile_repo.create(new_profile)
                context.profile_id = new_profile.id
                self.logger.info(f"Saved new user profile (ID: {new_profile.id})")
        except Exception as e:
            self.logger.error(f"Failed to save profile to database: {e}")
            raise
    
    async def run(self, context: ProfilingWorkflowContext) -> ProfilingWorkflowContext:
        """Process CV/PDF documents and build structured user profile.
        
        Args:
            context: The workflow context with user input and PDF paths
            
        Returns:
            Updated context with profile information
        """
        self.logger.info("Starting CV processing")
        
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
        context.raw_cv_text = raw_text
        
        # Use AI agent to structure the profile
        self.logger.info("Building structured profile using AI...")
        
        profiling_agent = Agent(model=self.model, output_type=ProfilingOutput)
        
        # Combine user-provided basic info with CV content
        basic_info_section = ""
        if context.basic_info:
            basic_info_section = f"\n\nAdditional Information Provided by User:\n{context.basic_info}"
        
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

Documents:
{raw_text}{basic_info_section}

Return a structured response with name, email, references (if any), and a detailed profile."""
        
        result = await profiling_agent.run(prompt)
        output = result.output
        
        # Update context with profile information
        context.user_profile = output.profile or ""
        context.references = output.references
        
        # Use extracted name/email from LLM (prefer user-provided, fallback to LLM)
        if not context.name:
            context.name = output.name
        if not context.email:
            context.email = output.email
        
        # If profile is empty, add error
        if not context.user_profile:
            context.add_error("Profile was built but is empty. Check PDF files and LLM output.")
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
