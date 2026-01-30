"""
Cover letter fabrication module using Pydantic AI agent.

This module retrieves matched jobs, company research, and user profiles from the database,
then uses a Pydantic AI agent to fabricate tailored cover letter topics and content.
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict

# Add project root to Python path if running directly
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from pydantic_ai import Agent
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

from src.database.models import (
    MatchedJob,
    JobPosting,
    UserProfile,
    CompanyResearch,
    Run,
    CoverLetter,
    Artifact,
)
from src.database.repository import GenericRepository
from src.database.session import db_session
from datetime import datetime
from src.fabrication.fab_cv import (
    CVFabricationAgent,
    render_cv_to_html,
    html_to_pdfbolt,
)


class CoverLetterTopic(BaseModel):
    """Model for cover letter topic/summary."""

    topic: str = Field(
        description="A concise, compelling topic or theme for the cover letter (e.g., 'Innovation-Driven Problem Solver' or 'Passionate Full-Stack Developer')"
    )
    summary: str = Field(
        description="A brief 2-3 sentence summary of the key message the cover letter should convey"
    )


class CoverLetterContent(BaseModel):
    """Model for complete cover letter content."""

    subject_line: str = Field(
        description="Professional subject line for the cover letter email"
    )
    salutation: str = Field(
        description="Professional greeting (e.g., 'Dear Hiring Manager' or 'Dear [Company] Team')"
    )
    opening_paragraph: str = Field(
        description="Engaging opening paragraph that hooks the reader and introduces the candidate"
    )
    body_paragraphs: List[str] = Field(
        description="2-3 body paragraphs that connect the candidate's experience to the job requirements and company values"
    )
    closing_paragraph: str = Field(
        description="Professional closing paragraph expressing enthusiasm and next steps"
    )
    signature: str = Field(
        description="Professional closing (e.g., 'Sincerely,' or 'Best regards,') followed by candidate name"
    )


class CoverLetterFabricationAgent:
    """AI-powered agent for fabricating tailored cover letters."""

    def __init__(self, model: str = "google-gla:gemini-2.5-flash"):
        """Initialize the cover letter fabrication agent.

        Args:
            model: The AI model to use for cover letter generation
        """
        self.model = model
        self.topic_agent = Agent(model=model, output_type=CoverLetterTopic)
        self.content_agent = Agent(model=model, output_type=CoverLetterContent)

    async def generate_topic(
        self,
        user_profile: str,
        job_posting: JobPosting,
        company_research: str,
    ) -> CoverLetterTopic:
        """Generate a compelling cover letter topic based on user profile, job, and company research.

        Args:
            user_profile: The user's profile text
            job_posting: The job posting object
            company_research: The company research results

        Returns:
            CoverLetterTopic with topic and summary
        """
        prompt = f"""You are an expert career coach helping craft a compelling cover letter.

Based on the following information, generate a compelling cover letter topic and summary:

USER PROFILE:
{user_profile}

JOB POSTING:
- Title: {job_posting.title}
- Company: {job_posting.company_name}
- Location: {job_posting.location}
- Description: {job_posting.description[:500] if job_posting.description else "N/A"}

COMPANY RESEARCH:
{company_research}

Output language: write the topic and summary in the same language as the job description. If the job is in Traditional Chinese, write in Traditional Chinese; if in English, write in English.

Generate a compelling topic (a theme or angle) and a brief summary that connects the candidate's strengths to the job requirements and company values. The topic should be memorable and the summary should highlight the key message the cover letter should convey.
"""
        result = await self.topic_agent.run(prompt)
        return result.output

    async def generate_content(
        self,
        user_profile: str,
        job_posting: JobPosting,
        company_research: str,
        topic: CoverLetterTopic,
    ) -> CoverLetterContent:
        """Generate complete cover letter content.

        Args:
            user_profile: The user's profile text
            job_posting: The job posting object
            company_research: The company research results
            topic: The cover letter topic to guide the content

        Returns:
            CoverLetterContent with all sections of the cover letter
        """
        prompt = f"""You are an expert career coach writing a professional cover letter.

Write a complete, tailored cover letter based on the following information:

USER PROFILE:
{user_profile}

JOB POSTING:
- Title: {job_posting.title}
- Company: {job_posting.company_name}
- Location: {job_posting.location}
- Description: {job_posting.description if job_posting.description else "N/A"}

COMPANY RESEARCH:
{company_research}

COVER LETTER TOPIC & SUMMARY:
Topic: {topic.topic}
Summary: {topic.summary}

Output language: write the entire cover letter in the same language as the job description. If the job is in Traditional Chinese, write in Traditional Chinese; if in English, write in English.

Write a professional cover letter that:
1. Opens with a compelling hook that connects to the company's mission/values
2. Demonstrates how the candidate's experience aligns with the job requirements
3. Shows understanding of the company culture and values from the research
4. Highlights specific achievements or skills relevant to the role
5. Closes with enthusiasm and a clear call to action

Make it specific, authentic, and tailored to this particular company and role. Avoid generic phrases.
"""
        result = await self.content_agent.run(prompt)
        return result.output


def get_latest_matched_jobs(session: Session, limit: int = 1) -> List[MatchedJob]:
    """Retrieve the latest matched jobs from the database.

    Args:
        session: SQLAlchemy database session
        limit: Maximum number of matched jobs to retrieve (default: 1)

    Returns:
        List of MatchedJob objects
    """
    matched_job_repo = GenericRepository(session, MatchedJob)
    return matched_job_repo.get_latest(n=limit)


def get_job_posting(session: Session, job_posting_id: str) -> Optional[JobPosting]:
    """Retrieve a job posting by ID.

    Args:
        session: SQLAlchemy database session
        job_posting_id: UUID of the job posting (as string)

    Returns:
        JobPosting if found, None otherwise
    """
    job_posting_repo = GenericRepository(session, JobPosting)
    return job_posting_repo.get(job_posting_id)


def get_company_research(
    session: Session, job_posting_id: str
) -> Optional[CompanyResearch]:
    """Retrieve company research for a job posting.

    Args:
        session: SQLAlchemy database session
        job_posting_id: UUID of the job posting (as string)

    Returns:
        CompanyResearch if found, None otherwise
    """
    import uuid

    return (
        session.query(CompanyResearch)
        .filter_by(job_posting_id=uuid.UUID(job_posting_id))
        .first()
    )


def get_latest_user_profile(session: Session) -> Optional[UserProfile]:
    """Retrieve the latest user profile from the database.

    Args:
        session: SQLAlchemy database session

    Returns:
        UserProfile if found, None otherwise
    """
    user_profile_repo = GenericRepository(session, UserProfile)
    latest_profiles = user_profile_repo.get_latest(n=1)
    return latest_profiles[0] if latest_profiles else None


def get_user_profile_for_run(session: Session, run_id: str) -> Optional[UserProfile]:
    """Retrieve the user profile that owns the run (for correct name/email in CV and cover letter).

    Uses run.user_profile_id when set; otherwise falls back to latest user profile.

    Args:
        session: SQLAlchemy database session
        run_id: UUID of the run (as string)

    Returns:
        UserProfile if found, None otherwise
    """
    import uuid as uuid_module

    run = session.query(Run).filter_by(id=uuid_module.UUID(run_id)).first()
    if run and getattr(run, "user_profile_id", None):
        profile = session.query(UserProfile).filter_by(id=run.user_profile_id).first()
        if profile:
            return profile
    return get_latest_user_profile(session)


def save_artifact(
    session: Session,
    matched_job_id: str,
    cover_letter_data: Optional[dict] = None,
    cv_pdf_url: Optional[str] = None,
) -> Artifact:
    """
    Save/update artifact with cover letter and/or CV data.

    Args:
        session: SQLAlchemy database session
        matched_job_id: UUID of the matched job (as string)
        cover_letter_data: Optional dict with {"topic": {...}, "content": {...}}
        cv_pdf_url: Optional PDF URL from PdfBolt

    Returns:
        Artifact: The saved artifact record
    """
    import uuid

    # Check if artifact already exists
    existing = (
        session.query(Artifact)
        .filter_by(matched_job_id=uuid.UUID(matched_job_id))
        .first()
    )

    if existing:
        # Update existing
        if cover_letter_data is not None:
            existing.cover_letter = cover_letter_data
        if cv_pdf_url is not None:
            existing.cv = {"pdf_url": cv_pdf_url}
        existing.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(existing)
        return existing
    else:
        # Create new
        new_artifact = Artifact(
            matched_job_id=uuid.UUID(matched_job_id),
            cover_letter=cover_letter_data,
            cv={"pdf_url": cv_pdf_url} if cv_pdf_url else None,
        )
        session.add(new_artifact)
        session.commit()
        session.refresh(new_artifact)
        return new_artifact


def save_cover_letter(
    session: Session,
    matched_job_id: str,
    topic: CoverLetterTopic,
    content: CoverLetterContent,
) -> CoverLetter:
    """
    Save cover letter to database (backward compatibility wrapper).

    Also saves to Artifact table for unified storage.

    Args:
        session: SQLAlchemy database session
        matched_job_id: UUID of the matched job (as string)
        topic: CoverLetterTopic object
        content: CoverLetterContent object

    Returns:
        CoverLetter: The saved cover letter record
    """
    import uuid

    cover_letter_data = {"topic": topic.model_dump(), "content": content.model_dump()}

    # Save to Artifact table
    save_artifact(session, matched_job_id, cover_letter_data=cover_letter_data)

    # Also save to CoverLetter table for backward compatibility
    existing = (
        session.query(CoverLetter)
        .filter_by(matched_job_id=uuid.UUID(matched_job_id))
        .first()
    )

    if existing:
        existing.topic = topic.model_dump()
        existing.content = content.model_dump()
        existing.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(existing)
        return existing
    else:
        new_cover_letter = CoverLetter(
            matched_job_id=uuid.UUID(matched_job_id),
            topic=topic.model_dump(),
            content=content.model_dump(),
        )
        session.add(new_cover_letter)
        session.commit()
        session.refresh(new_cover_letter)
        return new_cover_letter


async def fabricate_application_materials_for_job(
    session: Session,
    matched_job: MatchedJob,
    cover_letter_agent: CoverLetterFabricationAgent,
    cv_agent: Optional[CVFabricationAgent] = None,
    max_retries: int = 3,
) -> Optional[dict]:
    """Fabricate cover letter and CV for a specific matched job.
    Updates MatchedJob and Run status tracking.

    Args:
        session: SQLAlchemy database session
        matched_job: The matched job object
        cover_letter_agent: The cover letter fabrication agent
        cv_agent: Optional CV fabrication agent (created if None)
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        Dictionary containing topic, content, and CV PDF URL if successful, None if failed
    """
    # Update status to processing
    matched_job.fabrication_status = "processing"
    matched_job.fabrication_attempts += 1
    session.commit()

    # Initialize CV agent if not provided
    if cv_agent is None:
        # Use same model as cover letter agent
        cv_agent = CVFabricationAgent(model=cover_letter_agent.model)

    print(f"\n{'=' * 80}")
    print(f"FABRICATING APPLICATION MATERIALS FOR: {matched_job.id}")
    print(f"{'=' * 80}")

    try:
        # Step 1: Retrieve job posting
        print("\n1. Retrieving job posting...")
        job_posting = get_job_posting(session, str(matched_job.job_posting_id))
        if not job_posting:
            raise ValueError(f"Job posting {matched_job.job_posting_id} not found")
        print(f"   ✓ Found: {job_posting.title} at {job_posting.company_name}")

        # Step 2: Retrieve company research
        print("\n2. Retrieving company research...")
        company_research_obj = get_company_research(
            session, str(matched_job.job_posting_id)
        )
        if not company_research_obj:
            print(
                f"   ⚠️  No company research found for job posting {matched_job.job_posting_id}"
            )
            print("   → Using job posting description only")
            company_research = (
                job_posting.description or "No company research available"
            )
        else:
            print(f"   ✓ Found company research (ID: {company_research_obj.id})")
            company_research = company_research_obj.research_results

        # Step 3: Retrieve user profile (use run owner so CV/cover letter get correct name and email)
        print("\n3. Retrieving user profile...")
        if matched_job.run_id:
            user_profile_obj = get_user_profile_for_run(
                session, str(matched_job.run_id)
            )
        else:
            user_profile_obj = get_latest_user_profile(session)
        if not user_profile_obj:
            raise ValueError("No user profile found in database")
        print(
            f"   ✓ Found user profile: {user_profile_obj.name} ({user_profile_obj.email})"
        )
        user_profile = user_profile_obj.profile_text

        # Step 4: Generate cover letter topic
        print("\n4. Generating cover letter topic...")
        topic = await cover_letter_agent.generate_topic(
            user_profile=user_profile,
            job_posting=job_posting,
            company_research=company_research,
        )
        print(f"   ✓ Topic: {topic.topic}")
        print(f"   → Summary: {topic.summary}")

        # Step 5: Generate cover letter content
        print("\n5. Generating cover letter content...")
        content = await cover_letter_agent.generate_content(
            user_profile=user_profile,
            job_posting=job_posting,
            company_research=company_research,
            topic=topic,
        )
        print("   ✓ Cover letter generated successfully")
        print(f"   → Subject: {content.subject_line}")
        print(f"   → Body paragraphs: {len(content.body_paragraphs)}")

        # Step 6: Generate CV (pass applicant contact from DB so CV uses real email, not placeholders)
        print("\n6. Generating tailored CV...")
        refs = user_profile_obj.references
        applicant_phone = None
        applicant_linkedin = None
        if isinstance(refs, dict):
            applicant_phone = refs.get("phone") or refs.get("phone_number")
            applicant_linkedin = refs.get("linkedin") or refs.get("linkedin_url")
        cv = await cv_agent.generate_tailored_cv(
            user_profile=user_profile,
            job_posting_title=job_posting.title or "",
            job_posting_company=job_posting.company_name or "",
            job_posting_description=job_posting.description or "",
            company_research=company_research,
            applicant_name=user_profile_obj.name,
            applicant_email=user_profile_obj.email,
            applicant_phone=applicant_phone,
            applicant_linkedin=applicant_linkedin,
        )
        print("   ✓ CV generated successfully")
        print(f"   → Name: {cv.name}")
        print(f"   → Sections: {len(cv.sections)}")

        # Step 7: Render CV to HTML and convert to PDF
        print("\n7. Converting CV to PDF via PdfBolt...")
        html = render_cv_to_html(cv)
        pdf_url = html_to_pdfbolt(html)
        print(f"   ✓ PDF generated: {pdf_url}")

        # Step 8: Save to database
        print("\n8. Saving artifacts to database...")
        cover_letter_data = {
            "topic": topic.model_dump(),
            "content": content.model_dump(),
        }
        saved_artifact = save_artifact(
            session=session,
            matched_job_id=str(matched_job.id),
            cover_letter_data=cover_letter_data,
            cv_pdf_url=pdf_url,
        )
        print(f"   ✓ Artifact saved (ID: {saved_artifact.id})")

        # Also save cover letter to old table for backward compatibility
        saved_cover_letter = save_cover_letter(
            session=session,
            matched_job_id=str(matched_job.id),
            topic=topic,
            content=content,
        )

        # Update matched job status (only increment counter if status changed)
        was_completed = matched_job.fabrication_status == "completed"
        matched_job.fabrication_status = "completed"
        matched_job.fabrication_completed_at = datetime.utcnow()
        matched_job.fabrication_error = None

        # Update run counters only if status changed from non-completed to completed
        if matched_job.run_id and not was_completed:
            run = session.query(Run).filter_by(id=matched_job.run_id).first()
            if run:
                run.fabrication_completed_count += 1
                session.commit()

        session.commit()

        return {
            "matched_job_id": str(matched_job.id),
            "job_posting_id": str(job_posting.id),
            "job_title": job_posting.title,
            "company_name": job_posting.company_name,
            "topic": topic.model_dump(),
            "content": content.model_dump(),
            "cv_pdf_url": pdf_url,
        }

    except Exception as e:
        # Handle failure
        error_msg = str(e)
        matched_job.fabrication_status = (
            "failed" if matched_job.fabrication_attempts >= max_retries else "pending"
        )
        matched_job.fabrication_error = error_msg

        # Update run counters (only increment failed count if marking as failed for first time)
        was_failed = matched_job.fabrication_status == "failed"
        if (
            matched_job.run_id
            and matched_job.fabrication_attempts >= max_retries
            and not was_failed
        ):
            run = session.query(Run).filter_by(id=matched_job.run_id).first()
            if run:
                run.fabrication_failed_count += 1
                session.commit()

        session.commit()

        print(
            f"   ❌ Fabrication failed (attempt {matched_job.fabrication_attempts}/{max_retries}): {error_msg}"
        )

        if matched_job.fabrication_attempts < max_retries:
            print("   → Will retry later")
        else:
            print("   → Max retries exceeded, marking as failed")

        return None


async def fabricate_matched_jobs_for_run(
    session: Session,
    run_id: str,
    model: str = "google-gla:gemini-2.5-flash",
    max_retries: int = 3,
) -> Dict[str, int]:
    """
    Fabricate cover letters for all matched jobs in a run that have completed research.

    Args:
        session: SQLAlchemy database session
        run_id: UUID of the run (as string)
        model: AI model to use for generation
        max_retries: Maximum number of retry attempts per job

    Returns:
        Dictionary with counts: {'successful': int, 'failed': int, 'total': int}
    """
    import uuid

    # Get all matched jobs for this run that have completed research
    matched_jobs = (
        session.query(MatchedJob)
        .filter_by(run_id=uuid.UUID(run_id), research_status="completed")
        .all()
    )

    if not matched_jobs:
        print(f"No matched jobs with completed research found for run {run_id}")
        return {"successful": 0, "failed": 0, "total": 0}

    print(f"\n{'=' * 80}")
    print(
        f"FABRICATING COVER LETTERS FOR {len(matched_jobs)} MATCHED JOBS (RUN {run_id})"
    )
    print(f"{'=' * 80}\n")

    # Initialize agent
    agent = CoverLetterFabricationAgent(model=model)

    successful = 0
    failed = 0

    for i, matched_job in enumerate(matched_jobs, 1):
        print(f"\n[{i}/{len(matched_jobs)}] Processing matched job {matched_job.id}")

        # Skip if already completed
        if matched_job.fabrication_status == "completed":
            print("   ⏭️  Fabrication already completed, skipping")
            successful += 1
            continue

        # Skip if max retries exceeded
        if (
            matched_job.fabrication_attempts >= max_retries
            and matched_job.fabrication_status == "failed"
        ):
            print("   ⏭️  Max retries exceeded, skipping")
            failed += 1
            continue

        # Perform fabrication
        cv_agent = CVFabricationAgent(model=model)
        result = await fabricate_application_materials_for_job(
            session=session,
            matched_job=matched_job,
            cover_letter_agent=agent,
            cv_agent=cv_agent,
            max_retries=max_retries,
        )

        if result:
            successful += 1
            print("   ✓ Fabrication completed successfully")
        else:
            failed += 1

    print("\n" + "=" * 80)
    print("FABRICATION SUMMARY")
    print("=" * 80)
    print(f"Total: {len(matched_jobs)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    return {"successful": successful, "failed": failed, "total": len(matched_jobs)}


async def fabricate_cover_letters_for_latest_jobs(
    limit: int = 5,
    model: str = "google-gla:gemini-2.5-flash",
) -> List[dict]:
    """Fabricate cover letters for the latest matched jobs.

    Args:
        limit: Maximum number of matched jobs to process
        model: AI model to use for generation

    Returns:
        List of dictionaries containing cover letter data
    """
    print("=" * 80)
    print("COVER LETTER FABRICATION SCRIPT")
    print("=" * 80)

    # Initialize agent
    agent = CoverLetterFabricationAgent(model=model)

    # Get database session
    session_gen = db_session()
    session = next(session_gen)

    results = []

    try:
        print(f"\nRetrieving latest {limit} matched jobs...")
        matched_jobs = get_latest_matched_jobs(session, limit=limit)

        if not matched_jobs:
            print("   ❌ No matched jobs found in database")
            print("   → Make sure you have run the matching workflow first")
            return results

        print(f"   ✓ Found {len(matched_jobs)} matched job(s)")

        # Process each matched job
        for i, matched_job in enumerate(matched_jobs, 1):
            print(f"\n{'=' * 80}")
            print(f"PROCESSING JOB {i}/{len(matched_jobs)}")
            print(f"{'=' * 80}")

            cv_agent = CVFabricationAgent(model=model)
            result = await fabricate_application_materials_for_job(
                session=session,
                matched_job=matched_job,
                cover_letter_agent=agent,
                cv_agent=cv_agent,
            )

            if result:
                results.append(result)
                print(f"\n✓ Successfully fabricated cover letter for job {i}")

        print(f"\n{'=' * 80}")
        print("SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total jobs processed: {len(matched_jobs)}")
        print(f"Successfully fabricated: {len(results)}")
        print(f"Failed: {len(matched_jobs) - len(results)}")

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        print("\nClosing database session...")
        try:
            next(session_gen, None)  # Consume generator to trigger commit
        except StopIteration:
            pass
        session.close()
        print("   ✓ Database session closed")

    return results


if __name__ == "__main__":
    """
    EXECUTION FLOW:
    1. Retrieve latest matched jobs from database
    2. For each matched job:
       a. Retrieve the job posting
       b. Retrieve company research (or use job description as fallback)
       c. Retrieve user profile
       d. Generate cover letter topic using Pydantic AI agent
       e. Generate complete cover letter content using Pydantic AI agent
    3. Return results with topic and content for each job
    """
    import asyncio

    # Run the async function
    results = asyncio.run(fabricate_cover_letters_for_latest_jobs(limit=5))

    # Display results
    if results:
        print("\n" + "=" * 80)
        print("COVER LETTERS FABRICATED")
        print("=" * 80)
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['job_title']} at {result['company_name']}")
            print(f"   Topic: {result['topic']['topic']}")
            print(f"   Subject: {result['content']['subject_line']}")
