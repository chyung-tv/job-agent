"""CV fabrication module using Pydantic AI agent."""

import base64
import os
from pathlib import Path
from typing import Optional

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic_ai import Agent

from src.fabrication.cv_models import TailoredCV

# Template path
TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_PATH = TEMPLATE_DIR / "cv_template.html"
PDFBOLT_API_URL = "https://api.pdfbolt.com/v1/sync"

# System prompt for CV generation
CV_SYSTEM_PROMPT = """
You are a Senior Technical Recruiter. Your job is to take a raw candidate profile
and a specific job description, and produce a tailored CV in JSON format that
strictly matches the TailoredCV schema described below. Do not output any
explanations, commentary, or markdown – only a single valid JSON object.

Schema (informal):
- TailoredCV:
  - name: string
  - email: string
  - phone: string
  - linkedin: optional string
  - summary: 2-3 sentence profile tailored to the job description
  - sections: list of CVSection
- CVSection:
  - title: string (e.g. \"Professional Experience\", \"Projects\", \"Education\")
  - entries: list of CVEntry
- CVEntry:
  - heading: string (e.g. Company name or University)
  - subheading: string (e.g. Job title or Degree)
  - dates: string (e.g. \"2020 - Present\")
  - bullets: list of bullet strings

Rules:
- Omit sections that are clearly not relevant to the job (e.g. \"Medical Background\"
  for non-medical roles).
- Prefer concise, impact-focused bullet points.
- Use at most 5 bullets per entry.
- Extract phone and linkedin from the user profile if available.
"""


class CVFabricationAgent:
    """AI-powered agent for fabricating tailored CVs."""

    def __init__(self, model: str = "google-gla:gemini-2.5-flash"):
        """Initialize the CV fabrication agent.

        Args:
            model: The AI model to use for CV generation
        """
        self.agent = Agent(model=model, system_prompt=CV_SYSTEM_PROMPT, output_type=TailoredCV)

    async def generate_tailored_cv(
        self,
        user_profile: str,
        job_posting_title: str,
        job_posting_company: str,
        job_posting_description: str,
        company_research: str,
    ) -> TailoredCV:
        """Generate a tailored CV based on user profile, job, and company research.

        Args:
            user_profile: The user's profile text
            job_posting_title: The job title
            job_posting_company: The company name
            job_posting_description: The full job description
            company_research: The company research results

        Returns:
            TailoredCV object
        """
        prompt = f"""Generate a tailored CV for this job application.

USER PROFILE:
{user_profile}

JOB POSTING:
- Title: {job_posting_title}
- Company: {job_posting_company}
- Description: {job_posting_description[:1000] if len(job_posting_description) > 1000 else job_posting_description}

COMPANY RESEARCH:
{company_research}

Generate a CV that:
1. Highlights relevant experience and skills for this specific role
2. Tailors the summary to match the job requirements
3. Emphasizes achievements that align with the company's values and needs
4. Uses concise, impact-focused bullet points
5. Omits irrelevant sections
"""
        result = await self.agent.run(prompt)
        return result.output


def render_cv_to_html(cv: TailoredCV) -> str:
    """Render the CV into HTML using the Jinja2 template.

    Args:
        cv: TailoredCV object to render

    Returns:
        Rendered HTML string
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(TEMPLATE_PATH.name)
    # Apply bullet capping before rendering.
    capped_cv = cv.with_bullet_cap(max_bullets=5)
    return template.render(cv=capped_cv)


def html_to_pdfbolt(html: str) -> str:
    """Send HTML to PdfBolt and return the hosted PDF URL.

    Args:
        html: HTML string to convert to PDF

    Returns:
        PDF URL from PdfBolt

    Raises:
        RuntimeError: If PDFBOLTS_API_KEY is not set or API call fails
    """
    api_key = os.getenv("PDFBOLTS_API_KEY")
    if not api_key:
        raise RuntimeError("PDFBOLTS_API_KEY is not set in the environment.")

    base64_html = base64.b64encode(html.encode("utf-8")).decode("ascii")
    payload = {
        "html": base64_html,
        "margin": {
            "top": "0.5in",
            "left": "0.5in",
        },
    }
    headers = {
        "API-KEY": api_key,
        "Content-Type": "application/json",
    }

    response = requests.post(
        PDFBOLT_API_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    # Expected shape: { "documentUrl": "<https link>", ... }
    return data["documentUrl"]
