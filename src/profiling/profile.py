"""Profiling step: Extract and build user profile from PDF documents."""

from pathlib import Path
from typing import Optional, TYPE_CHECKING
from pydantic_ai import Agent
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .pdf_parser import PDFParser

load_dotenv()

# Optional database imports
try:
    from src.database import db_session, GenericRepository, UserProfile
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

if TYPE_CHECKING:
    from src.workflow.base_context import JobSearchWorkflowContext as WorkflowContext  # Alias for backward compatibility


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


def build_profile_from_pdfs(pdf_paths: list[Path]) -> str:
    """Extract and combine text from multiple PDF documents.
    
    Args:
        pdf_paths: List of paths to PDF files to parse
        
    Returns:
        Combined extracted text from all PDFs
    """
    parser = PDFParser()
    all_text = []
    
    for pdf_path in pdf_paths:
        if not pdf_path.exists():
            print(f"[WARNING] File not found: {pdf_path.name}, skipping...")
            continue
            
        print(f"Parsing {pdf_path.name}...")
        try:
            text = parser.parse(pdf_path)
            all_text.append(f"--- Content from {pdf_path.name} ---\n{text}")
        except Exception as e:
            print(f"[ERROR] Failed to parse {pdf_path.name}: {e}")
    
    return "\n\n".join(all_text)


def _extract_name_email_from_text(raw_text: str) -> tuple[str | None, str | None]:
    """Extract name and email from raw PDF text using simple patterns.
    
    Args:
        raw_text: Raw text extracted from PDFs
        
    Returns:
        Tuple of (name, email) if found, (None, None) otherwise
    """
    import re
    
    # Try to extract email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, raw_text)
    email = emails[0] if emails else None
    
    # Try to extract name (look for common patterns at the beginning)
    # This is a simple heuristic - the LLM will extract it more accurately
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


def _load_profile_from_db(name: str, email: str) -> Optional[str]:
    """Load user profile from database if it exists for the given name and email.
    
    Args:
        name: User's name
        email: User's email
        
    Returns:
        Profile text if found, None otherwise
    """
    if not DB_AVAILABLE or not name or not email:
        return None
    
    try:
        session_gen = db_session()
        session = next(session_gen)
        try:
            profile_repo = GenericRepository(session, UserProfile)
            # Find profile with matching name and email
            profile = profile_repo.find_one(name=name, email=email)
            if profile:
                print(f"[DATABASE] Found cached user profile for {name} ({email})")
                # Update last_used_at
                from datetime import datetime
                profile.last_used_at = datetime.utcnow()
                profile_repo.update(profile)
                return profile.profile_text
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass
    except Exception as e:
        print(f"[WARNING] Failed to load profile from database: {e}")
    
    return None


def _save_profile_to_db(
    name: str,
    email: str,
    profile_text: str,
    references: Optional[dict],
    pdf_paths: list[Path],
) -> None:
    """Save user profile to database.
    
    Args:
        name: User's name
        email: User's email
        profile_text: The structured profile text
        references: Optional references (LinkedIn, portfolio, etc.)
        pdf_paths: List of PDF file paths used to generate the profile
    """
    if not DB_AVAILABLE or not name or not email:
        return
    
    try:
        pdf_paths_str = [str(p) for p in pdf_paths]
        
        session_gen = db_session()
        session = next(session_gen)
        try:
            profile_repo = GenericRepository(session, UserProfile)
            
            # Check if profile with this name and email already exists
            existing = profile_repo.find_one(name=name, email=email)
            if existing:
                # Update existing profile
                existing.profile_text = profile_text
                existing.references = references
                existing.source_pdfs = pdf_paths_str
                profile_repo.update(existing)
                print(f"[DATABASE] Updated existing user profile (ID: {existing.id})")
            else:
                # Create new profile
                import uuid
                new_profile = UserProfile(
                    id=uuid.uuid4(),
                    name=name,
                    email=email,
                    profile_text=profile_text,
                    references=references,
                    source_pdfs=pdf_paths_str,
                )
                profile_repo.create(new_profile)
                print(f"[DATABASE] Saved new user profile (ID: {new_profile.id})")
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass
    except Exception as e:
        print(f"[WARNING] Failed to save profile to database: {e}")




def build_user_profile(
    context: "WorkflowContext",
    model: str = "google-gla:gemini-2.5-flash",
    use_cache: bool = True,
) -> "WorkflowContext":
    """Build user profile using WorkflowContext (Context Object Pattern).
    
    Updates the context with user_profile, profile_was_cached, profile_name, and profile_email.
    
    This function will:
    1. Check database for cached profile (if use_cache=True)
    2. If not found or PDFs changed, extract from PDFs and call LLM
    3. Save profile to database for future use
    
    Args:
        context: WorkflowContext object containing pdf_paths and/or data_dir
        model: AI model to use for profile extraction
        use_cache: Whether to use cached profile from database (default: True)
        
    Returns:
        Updated WorkflowContext with profile information populated
    """
    # Set default data_dir if not provided (before validation)
    if context.data_dir is None and context.pdf_paths is None:
        # Default to data/ directory relative to project root
        context.data_dir = Path(__file__).parent.parent.parent / "data"
    
    if not context.validate_for_profiling():
        return context
    
    # Determine which PDFs to parse
    pdf_paths = context.pdf_paths
    if pdf_paths is None:
        data_dir = context.data_dir
        # Look for common PDF files
        common_files = ["linkdeln.pdf", "linkedin.pdf", "CV_YungCH.pdf", "cv.pdf", "resume.pdf"]
        pdf_paths = [data_dir / f for f in common_files if (data_dir / f).exists()]
    
    if not pdf_paths:
        context.add_error("No PDF files found to parse. Please provide pdf_paths or ensure PDFs exist in data directory.")
        raise ValueError("No PDF files found to parse. Please provide pdf_paths or ensure PDFs exist in data directory.")
    
    # Extract text from PDFs first (needed for name/email extraction and LLM)
    print("=" * 80)
    print("Step 1: Extracting text from PDF documents...")
    print("=" * 80)
    raw_text = build_profile_from_pdfs(pdf_paths)
    
    # Try to extract name and email from raw text (for cache lookup)
    name, email = _extract_name_email_from_text(raw_text)
    
    # Try to load from database cache using name and email
    was_cached = False
    profile_text = None
    if use_cache and name and email:
        cached_profile = _load_profile_from_db(name, email)
        if cached_profile:
            profile_text = cached_profile
            was_cached = True
    
    # If not cached, use AI agent to structure the profile
    if not profile_text:
        print("\n" + "=" * 80)
        print("Step 2: Building structured profile using AI...")
        print("=" * 80)
        
        profiling_agent = Agent(model=model, output_type=ProfilingOutput)
        
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
        
        result = profiling_agent.run_sync(prompt)
        output = result.output
        
        # Use extracted name/email from LLM (more accurate than regex)
        name = output.name
        email = output.email
        profile_text = output.profile
        references = output.references
        
        # Save to database for future use
        _save_profile_to_db(
            name=name,
            email=email,
            profile_text=profile_text,
            references=references,
            pdf_paths=pdf_paths,
        )
    
    # Update context with profile information
    # Ensure profile_text is never None (use empty string if needed)
    context.user_profile = profile_text or ""
    context.profile_was_cached = was_cached
    context.profile_name = name
    context.profile_email = email
    
    # If profile is empty, add error
    if not context.user_profile:
        context.add_error("Profile was built but is empty. Check PDF files and LLM output.")
    
    return context