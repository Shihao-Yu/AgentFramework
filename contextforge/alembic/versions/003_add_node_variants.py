"""Add node_variants table for alternative phrasings

Revision ID: 003
Revises: 002
Create Date: 2026-01-14

This migration adds the node_variants table for storing alternative
question phrasings to improve search matching.
"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


SCHEMA = os.environ.get("DB_SCHEMA", "agent")

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {SCHEMA}.node_variants (
            id BIGSERIAL PRIMARY KEY,
            node_id BIGINT NOT NULL REFERENCES {SCHEMA}.knowledge_nodes(id) ON DELETE CASCADE,
            
            variant_text TEXT NOT NULL,
            embedding vector(1024),
            
            source VARCHAR(30) DEFAULT 'manual',
            source_reference VARCHAR(500),
            
            created_by VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            
            graph_version BIGINT DEFAULT 0
        );
        
        CREATE INDEX idx_variants_node ON {SCHEMA}.node_variants(node_id);
        CREATE INDEX idx_variants_graph_version ON {SCHEMA}.node_variants(graph_version);
        
        -- Vector index for variant embeddings
        CREATE INDEX idx_variants_embedding ON {SCHEMA}.node_variants 
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        WHERE embedding IS NOT NULL;
    """)
    
    # Add variant event trigger
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.emit_variant_event()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO {SCHEMA}.graph_events (event_type, entity_type, entity_id, payload)
                VALUES ('variant_created', 'variant', NEW.id, to_jsonb(NEW));
                RETURN NEW;
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO {SCHEMA}.graph_events (event_type, entity_type, entity_id, payload)
                VALUES ('variant_deleted', 'variant', OLD.id, to_jsonb(OLD));
                RETURN OLD;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER trg_variant_events
        AFTER INSERT OR DELETE ON {SCHEMA}.node_variants
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.emit_variant_event();
    """)


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_variant_events ON {SCHEMA}.node_variants;")
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.emit_variant_event();")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.node_variants;")
