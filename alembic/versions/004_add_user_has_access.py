"""add_user_has_access

Revision ID: 004
Revises: 003
Create Date: 2026-02-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, Sequence[str], None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add hasAccess column to user table for beta access control."""
    op.add_column(
        "user",
        sa.Column(
            "hasAccess",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Remove hasAccess column from user table."""
    op.drop_column("user", "hasAccess")
