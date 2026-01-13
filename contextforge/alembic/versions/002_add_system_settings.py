"""Add system_settings table for persisted configuration

Revision ID: 002
Revises: 001
Create Date: 2025-01-13

Simple key-value settings storage with one row per category.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE agent.system_settings (
            category VARCHAR(50) PRIMARY KEY,
            settings JSONB NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent.system_settings;")
