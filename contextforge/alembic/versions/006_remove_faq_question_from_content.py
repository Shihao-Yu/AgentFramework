"""Remove question field from FAQ content

Revision ID: 006
Revises: 005
Create Date: 2025-01-15

The FAQ node type had a redundant 'question' field in content that duplicated 
the node's 'title'. This migration:
1. Ensures title contains the question (using content.question if title is generic)
2. Removes the question key from FAQ content JSONB

After this migration, FAQ structure is:
- title: The question being asked
- content: { answer: "...", variants: [...] }
"""
import os
from typing import Sequence, Union

from alembic import op


SCHEMA = os.environ.get("DB_SCHEMA", "agent")

revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(f"""
        UPDATE {SCHEMA}.knowledge_nodes
        SET title = content->>'question'
        WHERE node_type = 'faq'
          AND content->>'question' IS NOT NULL
          AND content->>'question' != ''
          AND (
            title IS NULL 
            OR title = '' 
            OR title != content->>'question'
          );
    """)
    
    op.execute(f"""
        UPDATE {SCHEMA}.knowledge_nodes
        SET content = content - 'question'
        WHERE node_type = 'faq'
          AND content ? 'question';
    """)


def downgrade() -> None:
    op.execute(f"""
        UPDATE {SCHEMA}.knowledge_nodes
        SET content = jsonb_set(content, '{{question}}', to_jsonb(title))
        WHERE node_type = 'faq';
    """)
