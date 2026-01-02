"""Add last_call_at to rate_limit_tracking

Revision ID: 7a8b9c0d1e2f
Revises: 
Create Date: 2025-01-02

This migration adds the last_call_at column to rate_limit_tracking
so the UI can determine if rate limit data is stale.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '7a8b9c0d1e2f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add last_call_at column to rate_limit_tracking."""
    # Use execute for direct SQL - safer with TimescaleDB hypertables
    op.execute("""
        ALTER TABLE rate_limit_tracking 
        ADD COLUMN IF NOT EXISTS last_call_at TIMESTAMPTZ;
    """)


def downgrade():
    """Remove last_call_at column."""
    op.execute("""
        ALTER TABLE rate_limit_tracking 
        DROP COLUMN IF EXISTS last_call_at;
    """)
