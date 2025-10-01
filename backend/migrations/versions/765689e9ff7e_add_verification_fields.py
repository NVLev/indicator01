"""Add_verification_fields

Revision ID: 765689e9ff7e
Revises: 8750d6ccf923
Create Date: 2025-09-24 22:19:50.671104

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "765689e9ff7e"
down_revision: Union[str, Sequence[str], None] = "8750d6ccf923"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "studies",
        sa.Column(
            "needs_verification", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "studies", sa.Column("verification_results", sa.JSON(), nullable=True)
    )
    op.add_column("studies", sa.Column("verification_score", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("studies", "verification_score")
    op.drop_column("studies", "verification_results")
    op.drop_column("studies", "needs_verification")
