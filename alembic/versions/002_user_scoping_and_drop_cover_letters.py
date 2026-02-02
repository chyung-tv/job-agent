"""user_scoping_and_drop_cover_letters

Revision ID: 002
Revises: 001
Create Date: 2025-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add user_id to job_searches (nullable FK to user.id)
    op.add_column(
        "job_searches",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 2. Add user_id to matched_jobs (nullable FK to user.id)
    op.add_column(
        "matched_jobs",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 3. Data migration: copy cover_letters into artifacts
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE artifacts a
            SET cover_letter = (
                SELECT json_build_object('topic', cl.topic, 'content', cl.content)
                FROM cover_letters cl
                WHERE cl.matched_job_id = a.matched_job_id
            ),
            updated_at = now()
            WHERE EXISTS (
                SELECT 1 FROM cover_letters cl WHERE cl.matched_job_id = a.matched_job_id
            )
        """)
    )
    conn.execute(
        sa.text("""
            INSERT INTO artifacts (id, matched_job_id, cover_letter, cv, created_at, updated_at)
            SELECT gen_random_uuid(), cl.matched_job_id,
                   json_build_object('topic', cl.topic, 'content', cl.content),
                   NULL, now(), now()
            FROM cover_letters cl
            WHERE NOT EXISTS (
                SELECT 1 FROM artifacts a WHERE a.matched_job_id = cl.matched_job_id
            )
        """)
    )

    # 4. Drop cover_letters table
    op.drop_table("cover_letters")


def downgrade() -> None:
    # 1. Recreate cover_letters table (same structure as in 001)
    op.create_table(
        "cover_letters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "matched_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("matched_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("content", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("matched_job_id", name="uq_cover_letters_matched_job_id"),
    )

    # 2. Backfill cover_letters from artifacts.cover_letter (where cover_letter is not null)
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            INSERT INTO cover_letters (id, matched_job_id, topic, content, created_at, updated_at)
            SELECT gen_random_uuid(), a.matched_job_id,
                   a.cover_letter->'topic',
                   a.cover_letter->'content',
                   a.created_at, a.updated_at
            FROM artifacts a
            WHERE a.cover_letter IS NOT NULL
            ON CONFLICT (matched_job_id) DO NOTHING
        """)
    )

    # 3. Drop user_id from matched_jobs
    op.drop_column("matched_jobs", "user_id")

    # 4. Drop user_id from job_searches
    op.drop_column("job_searches", "user_id")
