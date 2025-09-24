"""Add task_id to Study model

Revision ID: 8750d6ccf923
Revises: 761dea2e62ff
Create Date: 2025-09-24 01:51:28.823743

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8750d6ccf923'
down_revision: Union[str, Sequence[str], None] = '761dea2e62ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('studies', sa.Column('task_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_studies_task_id'), 'studies', ['task_id'], unique=False)



def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_studies_task_id'), table_name='studies')
    op.drop_column('studies', 'task_id')
