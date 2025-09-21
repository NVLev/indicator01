"""Add Study model

Revision ID: 761dea2e62ff
Revises: e79a59e02cf7
Create Date: 2025-09-21 23:01:55.322609

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = '761dea2e62ff'
down_revision: Union[str, Sequence[str], None] = 'e79a59e02cf7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('studies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('path_to_study', sa.String(length=500), nullable=True),
    sa.Column('study_uid', sa.String(length=255), nullable=True),
    sa.Column('series_uid', sa.String(length=255), nullable=True),
    sa.Column('processing_status', sa.String(length=50), nullable=False),
    sa.Column('probability_of_pathology', sa.Float(), nullable=True),
    sa.Column('pathology', sa.Integer(), nullable=True),
    sa.Column('time_of_processing', sa.Float(), nullable=True),
    sa.Column('most_dangerous_pathology_type', sa.String(length=255), nullable=True),
    sa.Column('pathology_localization_coords', sa.JSON(), nullable=True),
    sa.Column('heatmap_path', sa.String(length=500), nullable=True),
    sa.Column('heatmap_format', sa.String(length=20), nullable=True),
    sa.Column('heatmap_metadata', sa.JSON(), nullable=True),
    sa.Column('total_instances', sa.Integer(), nullable=True),
    sa.Column('series_count', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('metadata_json', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('ready_for_inference', sa.Boolean(), nullable=False),
    sa.Column('inference_completed', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_studies_processing_status'), 'studies', ['processing_status'], unique=False)
    op.create_index(op.f('ix_studies_ready_for_inference'), 'studies', ['ready_for_inference'], unique=False)
    op.create_index(op.f('ix_studies_study_uid'), 'studies', ['study_uid'], unique=False)
    op.create_index(op.f('ix_studies_user_id'), 'studies', ['user_id'], unique=False)



def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(op.f('ix_studies_user_id'), table_name='studies')
    op.drop_index(op.f('ix_studies_study_uid'), table_name='studies')
    op.drop_index(op.f('ix_studies_ready_for_inference'), table_name='studies')
    op.drop_index(op.f('ix_studies_processing_status'), table_name='studies')
    op.drop_table('studies')

