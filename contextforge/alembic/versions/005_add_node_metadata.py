"""Add metadata column to knowledge_nodes

Revision ID: 005
Revises: 004
Create Date: 2025-01-15

Adds a JSONB metadata_ column for tenant-specific extensibility.
This is separate from the typed 'content' field and allows arbitrary
tenant-specific data without schema validation.

Use cases:
- Custom fields per tenant
- Feature flags
- Integration references (Zendesk, Jira, etc.)
- Tenant-specific display configuration
"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


SCHEMA = os.environ.get("DB_SCHEMA", "agent")

revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add metadata_ column to knowledge_nodes
    op.execute(f"""
        ALTER TABLE {SCHEMA}.knowledge_nodes
        ADD COLUMN metadata_ JSONB DEFAULT '{{}}';
    """)
    
    # Add GIN index for efficient JSONB queries
    op.execute(f"""
        CREATE INDEX idx_nodes_metadata ON {SCHEMA}.knowledge_nodes 
        USING gin(metadata_) 
        WHERE metadata_ IS NOT NULL AND metadata_ != '{{}}';
    """)


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.idx_nodes_metadata;")
    op.execute(f"ALTER TABLE {SCHEMA}.knowledge_nodes DROP COLUMN IF EXISTS metadata_;")
