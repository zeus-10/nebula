"""Add transcoding support

Revision ID: 5a8b2c3d4e5f
Revises: 66a7157dabcf
Create Date: 2025-12-23

Adds:
- transcoding_jobs table for tracking video transcoding tasks
- video_metadata and transcoded_variants columns to files table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5a8b2c3d4e5f'
down_revision: Union[str, None] = '66a7157dabcf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if transcoding_jobs table exists, create if not
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if 'transcoding_jobs' not in inspector.get_table_names():
        # Create transcoding_jobs table
        op.create_table(
            'transcoding_jobs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('file_id', sa.Integer(), nullable=False),
            sa.Column('target_quality', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
            sa.Column('progress', sa.Float(), nullable=True, server_default='0'),
            sa.Column('output_path', sa.String(length=500), nullable=True),
            sa.Column('output_size', sa.Integer(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('ffmpeg_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('celery_task_id', sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(['file_id'], ['files.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_transcoding_jobs_file_id'), 'transcoding_jobs', ['file_id'], unique=False)
        op.create_index(op.f('ix_transcoding_jobs_id'), 'transcoding_jobs', ['id'], unique=False)
        op.create_index(op.f('ix_transcoding_jobs_status'), 'transcoding_jobs', ['status'], unique=False)

    # Check if video_metadata column exists in files table, add if not
    files_columns = [col['name'] for col in inspector.get_columns('files')]
    if 'video_metadata' not in files_columns:
        op.add_column('files', sa.Column('video_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True))

    if 'transcoded_variants' not in files_columns:
        op.add_column('files', sa.Column('transcoded_variants', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Remove columns from files table
    op.drop_column('files', 'transcoded_variants')
    op.drop_column('files', 'video_metadata')

    # Drop transcoding_jobs table
    op.drop_index(op.f('ix_transcoding_jobs_status'), table_name='transcoding_jobs')
    op.drop_index(op.f('ix_transcoding_jobs_id'), table_name='transcoding_jobs')
    op.drop_index(op.f('ix_transcoding_jobs_file_id'), table_name='transcoding_jobs')
    op.drop_table('transcoding_jobs')
