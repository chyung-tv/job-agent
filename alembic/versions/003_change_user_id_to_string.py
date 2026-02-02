"""change_user_id_to_string

Revision ID: 003
Revises: 002
Create Date: 2026-02-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change user.id and related FKs from UUID to String."""
    # Drop foreign keys that reference user.id so we can alter column types safely.
    with op.batch_alter_table("session") as batch_op:
        batch_op.drop_constraint("session_userId_fkey", type_="foreignkey")

    with op.batch_alter_table("account") as batch_op:
        batch_op.drop_constraint("account_userId_fkey", type_="foreignkey")

    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_constraint("runs_user_id_fkey", type_="foreignkey")

    with op.batch_alter_table("job_searches") as batch_op:
        batch_op.drop_constraint("job_searches_user_id_fkey", type_="foreignkey")

    with op.batch_alter_table("matched_jobs") as batch_op:
        batch_op.drop_constraint("matched_jobs_user_id_fkey", type_="foreignkey")

    # Change primary key on user from UUID to String
    op.alter_column(
        "user",
        "id",
        type_=sa.String(length=255),
        existing_type=postgresql.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="id::text",
    )

    # Change all FKs that point to user.id from UUID to String
    op.alter_column(
        "runs",
        "user_id",
        type_=sa.String(length=255),
        existing_type=postgresql.UUID(as_uuid=True),
        postgresql_using="user_id::text",
    )

    op.alter_column(
        "job_searches",
        "user_id",
        type_=sa.String(length=255),
        existing_type=postgresql.UUID(as_uuid=True),
        postgresql_using="user_id::text",
    )

    op.alter_column(
        "matched_jobs",
        "user_id",
        type_=sa.String(length=255),
        existing_type=postgresql.UUID(as_uuid=True),
        postgresql_using="user_id::text",
    )

    op.alter_column(
        "session",
        "userId",
        type_=sa.String(length=255),
        existing_type=postgresql.UUID(as_uuid=True),
        postgresql_using='"userId"::text',
    )

    op.alter_column(
        "account",
        "userId",
        type_=sa.String(length=255),
        existing_type=postgresql.UUID(as_uuid=True),
        postgresql_using='"userId"::text',
    )

    # Recreate foreign keys with the same ondelete behavior
    with op.batch_alter_table("session") as batch_op:
        batch_op.create_foreign_key(
            "session_userId_fkey",
            "user",
            ["userId"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("account") as batch_op:
        batch_op.create_foreign_key(
            "account_userId_fkey",
            "user",
            ["userId"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("runs") as batch_op:
        batch_op.create_foreign_key(
            "runs_user_id_fkey",
            "user",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("job_searches") as batch_op:
        batch_op.create_foreign_key(
            "job_searches_user_id_fkey",
            "user",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("matched_jobs") as batch_op:
        batch_op.create_foreign_key(
            "matched_jobs_user_id_fkey",
            "user",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Revert user.id and related FKs back to UUID."""
    # Drop updated foreign keys
    with op.batch_alter_table("session") as batch_op:
        batch_op.drop_constraint("session_userId_fkey", type_="foreignkey")

    with op.batch_alter_table("account") as batch_op:
        batch_op.drop_constraint("account_userId_fkey", type_="foreignkey")

    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_constraint("runs_user_id_fkey", type_="foreignkey")

    with op.batch_alter_table("job_searches") as batch_op:
        batch_op.drop_constraint("job_searches_user_id_fkey", type_="foreignkey")

    with op.batch_alter_table("matched_jobs") as batch_op:
        batch_op.drop_constraint("matched_jobs_user_id_fkey", type_="foreignkey")

    # Change columns back to UUID
    op.alter_column(
        "user",
        "id",
        type_=postgresql.UUID(as_uuid=True),
        existing_type=sa.String(length=255),
        existing_nullable=False,
        postgresql_using="id::uuid",
    )

    op.alter_column(
        "runs",
        "user_id",
        type_=postgresql.UUID(as_uuid=True),
        existing_type=sa.String(length=255),
        postgresql_using="user_id::uuid",
    )

    op.alter_column(
        "job_searches",
        "user_id",
        type_=postgresql.UUID(as_uuid=True),
        existing_type=sa.String(length=255),
        postgresql_using="user_id::uuid",
    )

    op.alter_column(
        "matched_jobs",
        "user_id",
        type_=postgresql.UUID(as_uuid=True),
        existing_type=sa.String(length=255),
        postgresql_using="user_id::uuid",
    )

    op.alter_column(
        "session",
        "userId",
        type_=postgresql.UUID(as_uuid=True),
        existing_type=sa.String(length=255),
        postgresql_using='"userId"::uuid',
    )

    op.alter_column(
        "account",
        "userId",
        type_=postgresql.UUID(as_uuid=True),
        existing_type=sa.String(length=255),
        postgresql_using='"userId"::uuid',
    )

    # Recreate original foreign keys
    with op.batch_alter_table("session") as batch_op:
        batch_op.create_foreign_key(
            "session_userId_fkey",
            "user",
            ["userId"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("account") as batch_op:
        batch_op.create_foreign_key(
            "account_userId_fkey",
            "user",
            ["userId"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("runs") as batch_op:
        batch_op.create_foreign_key(
            "runs_user_id_fkey",
            "user",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("job_searches") as batch_op:
        batch_op.create_foreign_key(
            "job_searches_user_id_fkey",
            "user",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("matched_jobs") as batch_op:
        batch_op.create_foreign_key(
            "matched_jobs_user_id_fkey",
            "user",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )
