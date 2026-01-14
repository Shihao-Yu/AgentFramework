"""Update hybrid search to include node variants

Revision ID: 004
Revises: 003
Create Date: 2026-01-14

This migration updates the hybrid_search_nodes function to include
node_variants in the search results, improving search matching.
"""
import os
from typing import Sequence, Union

from alembic import op


SCHEMA = os.environ.get("DB_SCHEMA", "agent")

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.hybrid_search_nodes(
            query_text TEXT,
            query_embedding vector(1024),
            tenant_ids TEXT[],
            node_types TEXT[] DEFAULT NULL,
            tag_filter TEXT[] DEFAULT NULL,
            bm25_weight FLOAT DEFAULT 0.4,
            vector_weight FLOAT DEFAULT 0.6,
            result_limit INT DEFAULT 20,
            rrf_k INT DEFAULT 60
        )
        RETURNS TABLE (
            id BIGINT,
            tenant_id VARCHAR(100),
            node_type VARCHAR(50),
            title VARCHAR(500),
            summary TEXT,
            content JSONB,
            tags TEXT[],
            dataset_name VARCHAR(100),
            field_path VARCHAR(500),
            bm25_rank INT,
            vector_rank INT,
            bm25_score FLOAT,
            vector_score FLOAT,
            rrf_score FLOAT,
            match_source VARCHAR(20)
        ) AS $$
        WITH bm25_results AS (
            SELECT 
                n.id,
                'node' as source,
                ROW_NUMBER() OVER (ORDER BY ts_rank_cd(n.search_vector, plainto_tsquery('english', query_text)) DESC) as rank,
                ts_rank_cd(n.search_vector, plainto_tsquery('english', query_text)) as score
            FROM {SCHEMA}.knowledge_nodes n
            WHERE n.search_vector @@ plainto_tsquery('english', query_text)
              AND n.is_deleted = FALSE
              AND n.status = 'published'
              AND n.tenant_id = ANY(tenant_ids)
              AND (node_types IS NULL OR n.node_type = ANY(node_types))
              AND (tag_filter IS NULL OR n.tags && tag_filter)
            ORDER BY score DESC
            LIMIT result_limit * 2
        ),
        vector_node_results AS (
            SELECT 
                n.id,
                'node' as source,
                ROW_NUMBER() OVER (ORDER BY n.embedding <=> query_embedding) as rank,
                1 - (n.embedding <=> query_embedding) as score
            FROM {SCHEMA}.knowledge_nodes n
            WHERE n.embedding IS NOT NULL
              AND n.is_deleted = FALSE
              AND n.status = 'published'
              AND n.tenant_id = ANY(tenant_ids)
              AND (node_types IS NULL OR n.node_type = ANY(node_types))
              AND (tag_filter IS NULL OR n.tags && tag_filter)
            ORDER BY n.embedding <=> query_embedding
            LIMIT result_limit * 2
        ),
        vector_variant_results AS (
            SELECT 
                n.id,
                'variant' as source,
                ROW_NUMBER() OVER (ORDER BY v.embedding <=> query_embedding) as rank,
                1 - (v.embedding <=> query_embedding) as score
            FROM {SCHEMA}.node_variants v
            JOIN {SCHEMA}.knowledge_nodes n ON v.node_id = n.id
            WHERE v.embedding IS NOT NULL
              AND n.is_deleted = FALSE
              AND n.status = 'published'
              AND n.tenant_id = ANY(tenant_ids)
              AND (node_types IS NULL OR n.node_type = ANY(node_types))
              AND (tag_filter IS NULL OR n.tags && tag_filter)
            ORDER BY v.embedding <=> query_embedding
            LIMIT result_limit * 2
        ),
        all_vector_results AS (
            SELECT id, source, 
                   ROW_NUMBER() OVER (ORDER BY score DESC) as rank,
                   score
            FROM (
                SELECT id, source, score FROM vector_node_results
                UNION ALL
                SELECT id, source, score FROM vector_variant_results
            ) combined
        ),
        dedupe_vector AS (
            SELECT DISTINCT ON (id) id, source, rank, score
            FROM all_vector_results
            ORDER BY id, score DESC
        ),
        combined AS (
            SELECT 
                COALESCE(b.id, v.id) as id,
                COALESCE(v.source, 'node') as match_source,
                b.rank as bm25_rank,
                v.rank as vector_rank,
                COALESCE(b.score, 0) as bm25_score,
                COALESCE(v.score, 0) as vector_score,
                (
                    bm25_weight * COALESCE(1.0 / (rrf_k + b.rank), 0) +
                    vector_weight * COALESCE(1.0 / (rrf_k + v.rank), 0)
                ) as rrf_score
            FROM bm25_results b
            FULL OUTER JOIN dedupe_vector v ON b.id = v.id
        )
        SELECT 
            n.id,
            n.tenant_id,
            n.node_type,
            n.title,
            n.summary,
            n.content,
            n.tags,
            n.dataset_name,
            n.field_path,
            c.bm25_rank::INT,
            c.vector_rank::INT,
            c.bm25_score::FLOAT,
            c.vector_score::FLOAT,
            c.rrf_score::FLOAT,
            c.match_source::VARCHAR(20)
        FROM combined c
        JOIN {SCHEMA}.knowledge_nodes n ON c.id = n.id
        ORDER BY c.rrf_score DESC
        LIMIT result_limit;
        $$ LANGUAGE SQL STABLE;
    """)


def downgrade() -> None:
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.hybrid_search_nodes(
            query_text TEXT,
            query_embedding vector(1024),
            tenant_ids TEXT[],
            node_types TEXT[] DEFAULT NULL,
            tag_filter TEXT[] DEFAULT NULL,
            bm25_weight FLOAT DEFAULT 0.4,
            vector_weight FLOAT DEFAULT 0.6,
            result_limit INT DEFAULT 20,
            rrf_k INT DEFAULT 60
        )
        RETURNS TABLE (
            id BIGINT,
            tenant_id VARCHAR(100),
            node_type VARCHAR(50),
            title VARCHAR(500),
            summary TEXT,
            content JSONB,
            tags TEXT[],
            dataset_name VARCHAR(100),
            field_path VARCHAR(500),
            bm25_rank INT,
            vector_rank INT,
            bm25_score FLOAT,
            vector_score FLOAT,
            rrf_score FLOAT
        ) AS $$
        WITH bm25_results AS (
            SELECT 
                n.id,
                ROW_NUMBER() OVER (ORDER BY ts_rank_cd(n.search_vector, plainto_tsquery('english', query_text)) DESC) as rank,
                ts_rank_cd(n.search_vector, plainto_tsquery('english', query_text)) as score
            FROM {SCHEMA}.knowledge_nodes n
            WHERE n.search_vector @@ plainto_tsquery('english', query_text)
              AND n.is_deleted = FALSE
              AND n.status = 'published'
              AND n.tenant_id = ANY(tenant_ids)
              AND (node_types IS NULL OR n.node_type = ANY(node_types))
              AND (tag_filter IS NULL OR n.tags && tag_filter)
            ORDER BY score DESC
            LIMIT result_limit * 2
        ),
        vector_results AS (
            SELECT 
                n.id,
                ROW_NUMBER() OVER (ORDER BY n.embedding <=> query_embedding) as rank,
                1 - (n.embedding <=> query_embedding) as score
            FROM {SCHEMA}.knowledge_nodes n
            WHERE n.embedding IS NOT NULL
              AND n.is_deleted = FALSE
              AND n.status = 'published'
              AND n.tenant_id = ANY(tenant_ids)
              AND (node_types IS NULL OR n.node_type = ANY(node_types))
              AND (tag_filter IS NULL OR n.tags && tag_filter)
            ORDER BY n.embedding <=> query_embedding
            LIMIT result_limit * 2
        ),
        combined AS (
            SELECT 
                COALESCE(b.id, v.id) as id,
                b.rank as bm25_rank,
                v.rank as vector_rank,
                COALESCE(b.score, 0) as bm25_score,
                COALESCE(v.score, 0) as vector_score,
                (
                    bm25_weight * COALESCE(1.0 / (rrf_k + b.rank), 0) +
                    vector_weight * COALESCE(1.0 / (rrf_k + v.rank), 0)
                ) as rrf_score
            FROM bm25_results b
            FULL OUTER JOIN vector_results v ON b.id = v.id
        )
        SELECT 
            n.id,
            n.tenant_id,
            n.node_type,
            n.title,
            n.summary,
            n.content,
            n.tags,
            n.dataset_name,
            n.field_path,
            c.bm25_rank::INT,
            c.vector_rank::INT,
            c.bm25_score::FLOAT,
            c.vector_score::FLOAT,
            c.rrf_score::FLOAT
        FROM combined c
        JOIN {SCHEMA}.knowledge_nodes n ON c.id = n.id
        ORDER BY c.rrf_score DESC
        LIMIT result_limit;
        $$ LANGUAGE SQL STABLE;
    """)
