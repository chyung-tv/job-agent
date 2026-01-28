"""Pydantic models for CV generation."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CVEntry(BaseModel):
    """Model for a single CV entry (e.g., work experience, education)."""

    heading: str = Field(description="e.g. Company Name or University")
    subheading: str = Field(description="e.g. Job Title or Degree")
    dates: str = Field(description="e.g. 2020 - Present")
    bullets: List[str]


class CVSection(BaseModel):
    """Model for a CV section containing multiple entries."""

    title: str = Field(
        description="e.g. Professional Experience, Medical Background, or Projects"
    )
    entries: List[CVEntry]


class TailoredCV(BaseModel):
    """Model for a complete tailored CV."""

    name: str
    email: str
    phone: str
    linkedin: Optional[str]
    summary: str = Field(
        description="2-3 sentence profile tailored to the specific job description."
    )
    sections: List[CVSection] = Field(
        description="Dynamic sections selected by the agent based on relevance."
    )

    def with_bullet_cap(self, max_bullets: int = 5) -> "TailoredCV":
        """Return a copy where each entry's bullets are capped at max_bullets."""
        capped_sections: List[CVSection] = []
        for section in self.sections:
            new_entries: List[CVEntry] = []
            for entry in section.entries:
                new_entries.append(
                    entry.model_copy(update={"bullets": entry.bullets[:max_bullets]})
                )
            capped_sections.append(section.model_copy(update={"entries": new_entries}))
        return self.model_copy(update={"sections": capped_sections})
