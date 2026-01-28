"""Nylas service for sending job application packages via email."""

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from nylas import Client
from sqlalchemy.orm import Session

from src.database import UserProfile
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class NylasService:
    """Service for sending emails via Nylas API."""
    
    def __init__(self):
        """Initialize the Nylas service."""
        self.api_key = os.getenv("NYLAS_API_KEY")
        self.api_uri = os.getenv("NYLAS_API_URI", "https://api.nylas.com")
        self.grant_id = os.getenv("NYLAS_GRANT_ID")
        
        if not self.api_key:
            raise ValueError("NYLAS_API_KEY is not set in environment variables")
        if not self.grant_id:
            raise ValueError("NYLAS_GRANT_ID is not set in environment variables")
        
        self.client = Client(
            api_key=self.api_key,
            api_uri=self.api_uri
        )
        
        # Setup Jinja2 template environment
        template_dir = Path(__file__).parent / "template"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )
        self.template = self.env.get_template("email_template.html")
    
    def _get_user_profile(self, session: Session, user_email: Optional[str] = None) -> Optional[Dict]:
        """Get user profile information for email greeting.
        
        Args:
            session: Database session
            user_email: Optional user email to look up specific profile
            
        Returns:
            Dictionary with user name and email, or None if not found
        """
        try:
            if user_email:
                # Try to find profile by email
                profile = session.query(UserProfile).filter_by(email=user_email).first()
                if profile:
                    return {
                        "name": profile.name,
                        "email": profile.email,
                    }
            
            # Fallback: Get latest user profile
            profile = session.query(UserProfile).order_by(UserProfile.last_used_at.desc()).first()
            if profile:
                return {
                    "name": profile.name,
                    "email": profile.email,
                }
        except Exception as e:
            logger.warning(f"Failed to get user profile: {e}")
        
        return None
    
    def _format_cover_letter(self, cover_letter_data: Dict) -> str:
        """Format cover letter content into readable text.
        
        Args:
            cover_letter_data: Dictionary with cover letter topic and content
            
        Returns:
            Formatted cover letter text
        """
        if not cover_letter_data:
            return ""
        
        content = cover_letter_data.get("content", {})
        if not content:
            return ""
        
        # Build cover letter from structured content
        parts = []
        
        if content.get("salutation"):
            parts.append(content["salutation"])
            parts.append("")
        
        if content.get("opening_paragraph"):
            parts.append(content["opening_paragraph"])
            parts.append("")
        
        if content.get("body_paragraphs"):
            for paragraph in content["body_paragraphs"]:
                parts.append(paragraph)
                parts.append("")
        
        if content.get("closing_paragraph"):
            parts.append(content["closing_paragraph"])
            parts.append("")
        
        if content.get("signature"):
            parts.append(content["signature"])
        
        return "\n".join(parts)
    
    def _prepare_email_data(
        self,
        completed_items: List[Dict],
        user_profile: Optional[Dict] = None
    ) -> Dict:
        """Prepare data for email template.
        
        Args:
            completed_items: List of completed job items
            user_profile: Optional user profile with name and email
            
        Returns:
            Dictionary with data for email template
        """
        # Format jobs for template
        jobs = []
        for item in completed_items:
            cover_letter_text = self._format_cover_letter(item.get("cover_letter", {}))
            
            job_data = {
                "title": item.get("job_title", "N/A"),
                "company": item.get("company_name", "N/A"),
                "location": item.get("location", "N/A"),
                "description": item.get("job_description", ""),
                "match_reason": item.get("match_reason", ""),  # From MatchedJob.reason
                "cover_letter": cover_letter_text,
                "cv_pdf_url": item.get("cv", {}).get("pdf_url"),
                "application_link": item.get("application_link", {}).get("link") if item.get("application_link") else None,
            }
            jobs.append(job_data)
        
        return {
            "user_name": user_profile.get("name", "there") if user_profile else "there",
            "total_jobs": len(jobs),
            "jobs": jobs,
        }
    
    def send_job_application_email(
        self,
        session: Session,
        completed_items: List[Dict],
        recipient_email: Optional[str] = None,
    ) -> Dict:
        """Send email with job application packages.
        
        Args:
            session: Database session
            completed_items: List of completed job items with cover letters and CVs
            recipient_email: Optional recipient email (defaults to user profile email)
            
        Returns:
            Dictionary with send result
        """
        if not completed_items:
            logger.warning("No completed items to send")
            return {
                "success": False,
                "error": "No completed items to send",
            }
        
        try:
            # Get user profile for greeting
            user_profile = self._get_user_profile(session, recipient_email)
            
            # Use recipient email or user profile email
            email_to = recipient_email or (user_profile.get("email") if user_profile else None)
            if not email_to:
                raise ValueError("No recipient email provided and no user profile found")
            
            # Prepare email data
            email_data = self._prepare_email_data(completed_items, user_profile)
            
            # Render email HTML
            html_body = self.template.render(**email_data)
            
            # Prepare email subject
            subject = f"Your Job Application Packages ({email_data['total_jobs']} matched jobs)"
            
            # Send email via Nylas using messages.send() endpoint
            logger.info(f"Sending email to {email_to} with {len(completed_items)} job application(s)")
            
            # Send message directly with HTML body
            # Set is_plaintext=False to indicate HTML content
            message = self.client.messages.send(
                self.grant_id,
                request_body={
                    "to": [{"name": user_profile.get("name", "User") if user_profile else "User", "email": email_to}],
                    "subject": subject,
                    "body": html_body,
                    "is_plaintext": False,  # Indicate that body contains HTML
                }
            )
            
            if message and len(message) > 0:
                message_id = message[0].id
                logger.info(f"Email sent successfully. Message ID: {message_id}")
                
                return {
                    "success": True,
                    "message_id": message_id,
                    "recipient": email_to,
                    "items_sent": len(completed_items),
                }
            else:
                raise ValueError("Failed to send message")
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }
