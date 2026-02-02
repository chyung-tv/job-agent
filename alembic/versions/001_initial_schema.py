"""initial_schema

Revision ID: 001
Revises:
Create Date: 2025-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables from scratch (fresh init)."""
    # user (Better Auth + profile columns)
    op.create_table(
        "user",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("email", sa.String(255), nullable=False, server_default=""),
        sa.Column("emailVerified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("image", sa.String(500), nullable=True),
        sa.Column("createdAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updatedAt", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("profile_text", sa.Text(), nullable=True),
        sa.Column("suggested_job_titles", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("source_pdfs", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("references", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
    )

    # job_searches (no FK to user)
    op.create_table(
        "job_searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("query", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("google_domain", sa.String(50), server_default="google.com"),
        sa.Column("hl", sa.String(10), server_default="en"),
        sa.Column("gl", sa.String(10), server_default="us"),
        sa.Column("total_jobs_found", sa.Integer(), server_default="0"),
        sa.Column("jobs_screened", sa.Integer(), server_default="0"),
        sa.Column("matches_found", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # runs (FK to user, job_searches)
    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_search_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_searches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(255), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("total_matched_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("research_completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fabrication_completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("research_failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fabrication_failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("delivery_triggered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("delivery_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # job_postings
    op.create_table(
        "job_postings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_search_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_searches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("via", sa.String(255), nullable=True),
        sa.Column("share_link", sa.String(1000), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("extensions", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("detected_extensions", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("job_highlights", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("apply_options", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # matched_jobs
    op.create_table(
        "matched_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_search_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_searches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_posting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("is_match", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("job_description_summary", sa.Text(), nullable=True),
        sa.Column("application_link", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("research_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("research_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("research_error", sa.Text(), nullable=True),
        sa.Column("research_completed_at", sa.DateTime(), nullable=True),
        sa.Column("fabrication_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("fabrication_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fabrication_error", sa.Text(), nullable=True),
        sa.Column("fabrication_completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("job_posting_id", name="uq_matched_jobs_job_posting_id"),
    )

    # company_research
    op.create_table(
        "company_research",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("job_posting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("research_results", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("job_posting_id", name="uq_company_research_job_posting_id"),
    )

    # cover_letters
    op.create_table(
        "cover_letters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("matched_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matched_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("content", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("matched_job_id", name="uq_cover_letters_matched_job_id"),
    )

    # artifacts
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("matched_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matched_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cover_letter", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("cv", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("matched_job_id", name="uq_artifacts_matched_job_id"),
    )

    # Better Auth: session
    op.create_table(
        "session",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("userId", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column("expiresAt", sa.DateTime(), nullable=False),
        sa.Column("ipAddress", sa.String(255), nullable=True),
        sa.Column("userAgent", sa.String(500), nullable=True),
        sa.Column("createdAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updatedAt", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Better Auth: account
    op.create_table(
        "account",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("userId", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accountId", sa.String(255), nullable=False),
        sa.Column("providerId", sa.String(255), nullable=False),
        sa.Column("accessToken", sa.Text(), nullable=True),
        sa.Column("refreshToken", sa.Text(), nullable=True),
        sa.Column("accessTokenExpiresAt", sa.DateTime(), nullable=True),
        sa.Column("refreshTokenExpiresAt", sa.DateTime(), nullable=True),
        sa.Column("scope", sa.String(255), nullable=True),
        sa.Column("idToken", sa.Text(), nullable=True),
        sa.Column("password", sa.String(255), nullable=True),
        sa.Column("createdAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updatedAt", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Better Auth: verification
    op.create_table(
        "verification",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("identifier", sa.String(255), nullable=False),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("expiresAt", sa.DateTime(), nullable=False),
        sa.Column("createdAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updatedAt", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    """Drop all tables (reverse order of FKs)."""
    op.drop_table("verification")
    op.drop_table("account")
    op.drop_table("session")
    op.drop_table("artifacts")
    op.drop_table("cover_letters")
    op.drop_table("company_research")
    op.drop_table("matched_jobs")
    op.drop_table("job_postings")
    op.drop_table("runs")
    op.drop_table("job_searches")
    op.drop_table("user")
