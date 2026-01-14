"""Initial schema - consolidated from migrations 001-012

Revision ID: 001
Revises: 
Create Date: 2025-01-13

This single migration creates the complete FAQ Knowledge Base schema including:
- PostgreSQL extensions (vector, pg_trgm)
- Agent schema
- Knowledge nodes (unified graph model)
- Knowledge edges (relationships)
- Tenants (multi-tenant support)
- Staging nodes (review queue)
- Graph events (event sourcing)
- Hybrid search function
- All indexes and triggers

"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


SCHEMA = os.environ.get("DB_SCHEMA", "agent")

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # EXTENSIONS
    # =========================================================================
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    
    # =========================================================================
    # SCHEMA
    # =========================================================================
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    
    # =========================================================================
    # TENANTS TABLE
    # =========================================================================
    op.execute(f"""
        CREATE TABLE {SCHEMA}.tenants (
            id VARCHAR(100) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            settings JSONB DEFAULT '{{}}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        );
    """)
    
    op.execute(f"""
        INSERT INTO {SCHEMA}.tenants (id, name, description) VALUES 
        ('default', 'Default Tenant', 'Default tenant for migrated data'),
        ('shared', 'Shared', 'Shared concepts accessible to all tenants');
    """)
    
    # =========================================================================
    # USER TENANT ACCESS TABLE
    # =========================================================================
    op.execute(f"""
        CREATE TABLE {SCHEMA}.user_tenant_access (
            user_id VARCHAR(100) NOT NULL,
            tenant_id VARCHAR(100) NOT NULL REFERENCES {SCHEMA}.tenants(id) ON DELETE CASCADE,
            role VARCHAR(50) DEFAULT 'viewer',
            granted_at TIMESTAMPTZ DEFAULT NOW(),
            granted_by VARCHAR(100),
            PRIMARY KEY (user_id, tenant_id)
        );
        CREATE INDEX idx_user_tenant_user ON {SCHEMA}.user_tenant_access(user_id);
    """)
    
    # =========================================================================
    # KNOWLEDGE NODES TABLE (Unified)
    # =========================================================================
    op.execute(f"""
        CREATE TABLE {SCHEMA}.knowledge_nodes (
            id BIGSERIAL PRIMARY KEY,
            tenant_id VARCHAR(100) NOT NULL REFERENCES {SCHEMA}.tenants(id),
            node_type VARCHAR(50) NOT NULL,
            
            title VARCHAR(500) NOT NULL,
            summary TEXT,
            content JSONB NOT NULL,
            
            tags TEXT[] DEFAULT '{{}}',
            
            dataset_name VARCHAR(100),
            field_path VARCHAR(500),
            data_type VARCHAR(50),
            
            embedding vector(1024),
            search_vector tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('english', title), 'A') ||
                setweight(to_tsvector('english', COALESCE(summary, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(content->>'question', '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(content->>'answer', '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(content->>'description', '')), 'C')
            ) STORED,
            
            visibility VARCHAR(20) DEFAULT 'internal',
            status VARCHAR(20) DEFAULT 'published',
            source VARCHAR(50) DEFAULT 'manual',
            source_reference VARCHAR(500),
            
            version INTEGER DEFAULT 1,
            graph_version BIGINT DEFAULT 0,
            
            created_by VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_by VARCHAR(100),
            updated_at TIMESTAMPTZ,
            is_deleted BOOLEAN DEFAULT FALSE
        );
    """)
    
    # Node indexes
    op.execute(f"""
        CREATE INDEX idx_nodes_tenant ON {SCHEMA}.knowledge_nodes(tenant_id) WHERE NOT is_deleted;
        CREATE INDEX idx_nodes_type ON {SCHEMA}.knowledge_nodes(node_type) WHERE NOT is_deleted;
        CREATE INDEX idx_nodes_tenant_type ON {SCHEMA}.knowledge_nodes(tenant_id, node_type) WHERE NOT is_deleted;
        CREATE INDEX idx_nodes_dataset ON {SCHEMA}.knowledge_nodes(tenant_id, dataset_name) 
            WHERE dataset_name IS NOT NULL AND NOT is_deleted;
        CREATE INDEX idx_nodes_field_path ON {SCHEMA}.knowledge_nodes(field_path) 
            WHERE field_path IS NOT NULL AND NOT is_deleted;
        CREATE INDEX idx_nodes_tags ON {SCHEMA}.knowledge_nodes USING gin(tags) WHERE NOT is_deleted;
        CREATE INDEX idx_nodes_search ON {SCHEMA}.knowledge_nodes USING gin(search_vector) WHERE NOT is_deleted;
        CREATE INDEX idx_nodes_graph_version ON {SCHEMA}.knowledge_nodes(graph_version) WHERE NOT is_deleted;
        CREATE INDEX idx_nodes_status ON {SCHEMA}.knowledge_nodes(status) WHERE NOT is_deleted;
    """)
    
    # Vector index (HNSW)
    op.execute(f"""
        CREATE INDEX idx_nodes_embedding ON {SCHEMA}.knowledge_nodes 
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        WHERE embedding IS NOT NULL AND NOT is_deleted;
    """)
    
    # =========================================================================
    # KNOWLEDGE EDGES TABLE
    # =========================================================================
    op.execute(f"""
        CREATE TABLE {SCHEMA}.knowledge_edges (
            id BIGSERIAL PRIMARY KEY,
            source_id BIGINT NOT NULL REFERENCES {SCHEMA}.knowledge_nodes(id) ON DELETE CASCADE,
            target_id BIGINT NOT NULL REFERENCES {SCHEMA}.knowledge_nodes(id) ON DELETE CASCADE,
            edge_type VARCHAR(50) NOT NULL,
            weight FLOAT DEFAULT 1.0,
            is_auto_generated BOOLEAN DEFAULT FALSE,
            metadata_ JSONB DEFAULT '{{}}',
            
            created_by VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            
            UNIQUE(source_id, target_id, edge_type)
        );
        
        CREATE INDEX idx_edges_source ON {SCHEMA}.knowledge_edges(source_id);
        CREATE INDEX idx_edges_target ON {SCHEMA}.knowledge_edges(target_id);
        CREATE INDEX idx_edges_type ON {SCHEMA}.knowledge_edges(edge_type);
        CREATE INDEX idx_edges_auto ON {SCHEMA}.knowledge_edges(is_auto_generated);
    """)
    
    # =========================================================================
    # STAGING NODES TABLE
    # =========================================================================
    op.execute(f"""
        CREATE TABLE {SCHEMA}.staging_nodes (
            id BIGSERIAL PRIMARY KEY,
            tenant_id VARCHAR(100) NOT NULL REFERENCES {SCHEMA}.tenants(id),
            node_type VARCHAR(50) NOT NULL,
            title VARCHAR(500) NOT NULL,
            content JSONB NOT NULL,
            tags TEXT[] DEFAULT '{{}}',
            
            dataset_name VARCHAR(100),
            field_path VARCHAR(500),
            
            status VARCHAR(20) DEFAULT 'pending',
            action VARCHAR(20) NOT NULL,
            target_node_id BIGINT REFERENCES {SCHEMA}.knowledge_nodes(id),
            similarity FLOAT,
            
            source VARCHAR(50),
            source_reference VARCHAR(500),
            confidence FLOAT,
            
            reviewed_by VARCHAR(100),
            reviewed_at TIMESTAMPTZ,
            review_notes TEXT,
            
            created_by VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX idx_staging_tenant ON {SCHEMA}.staging_nodes(tenant_id);
        CREATE INDEX idx_staging_status ON {SCHEMA}.staging_nodes(status);
        CREATE INDEX idx_staging_action ON {SCHEMA}.staging_nodes(action);
    """)
    
    # =========================================================================
    # GRAPH EVENTS TABLE
    # =========================================================================
    op.execute(f"""
        CREATE TABLE {SCHEMA}.graph_events (
            id BIGSERIAL PRIMARY KEY,
            event_type VARCHAR(50) NOT NULL,
            entity_type VARCHAR(20) NOT NULL,
            entity_id BIGINT NOT NULL,
            payload JSONB,
            processed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX idx_graph_events_unprocessed ON {SCHEMA}.graph_events(created_at) 
            WHERE processed_at IS NULL;
        CREATE INDEX idx_graph_events_entity ON {SCHEMA}.graph_events(entity_type, entity_id);
    """)
    
    # =========================================================================
    # NODE VERSIONS TABLE
    # =========================================================================
    op.execute(f"""
        CREATE TABLE {SCHEMA}.node_versions (
            id BIGSERIAL PRIMARY KEY,
            node_id BIGINT NOT NULL REFERENCES {SCHEMA}.knowledge_nodes(id) ON DELETE CASCADE,
            version_number INTEGER NOT NULL,
            title VARCHAR(500) NOT NULL,
            content JSONB NOT NULL,
            tags TEXT[],
            change_type VARCHAR(50),
            changed_by VARCHAR(100),
            changed_at TIMESTAMPTZ DEFAULT NOW(),
            
            UNIQUE(node_id, version_number)
        );
        
        CREATE INDEX idx_node_versions_node ON {SCHEMA}.node_versions(node_id);
    """)
    
    # =========================================================================
    # KNOWLEDGE HITS TABLE (Analytics)
    # =========================================================================
    op.execute(f"""
        CREATE TABLE {SCHEMA}.knowledge_hits (
            id BIGSERIAL PRIMARY KEY,
            node_id BIGINT REFERENCES {SCHEMA}.knowledge_nodes(id) ON DELETE CASCADE,
            
            query_text TEXT,
            similarity_score FLOAT,
            
            retrieval_method VARCHAR(30),
            match_source VARCHAR(50),
            
            session_id VARCHAR(100),
            user_id VARCHAR(100),
            
            hit_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX idx_hits_node ON {SCHEMA}.knowledge_hits(node_id);
        CREATE INDEX idx_hits_time ON {SCHEMA}.knowledge_hits(hit_at DESC);
        CREATE INDEX idx_hits_session ON {SCHEMA}.knowledge_hits(session_id);
    """)
    
    # =========================================================================
    # TRIGGERS
    # =========================================================================
    
    # Node events trigger
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.emit_node_event()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO {SCHEMA}.graph_events (event_type, entity_type, entity_id, payload)
                VALUES ('node_created', 'node', NEW.id, to_jsonb(NEW));
                RETURN NEW;
            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.is_deleted = FALSE AND NEW.is_deleted = TRUE THEN
                    INSERT INTO {SCHEMA}.graph_events (event_type, entity_type, entity_id, payload)
                    VALUES ('node_deleted', 'node', NEW.id, to_jsonb(NEW));
                ELSE
                    INSERT INTO {SCHEMA}.graph_events (event_type, entity_type, entity_id, payload)
                    VALUES ('node_updated', 'node', NEW.id, to_jsonb(NEW));
                END IF;
                RETURN NEW;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER trg_node_events
        AFTER INSERT OR UPDATE ON {SCHEMA}.knowledge_nodes
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.emit_node_event();
    """)
    
    # Edge events trigger
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.emit_edge_event()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO {SCHEMA}.graph_events (event_type, entity_type, entity_id, payload)
                VALUES ('edge_created', 'edge', NEW.id, to_jsonb(NEW));
                RETURN NEW;
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO {SCHEMA}.graph_events (event_type, entity_type, entity_id, payload)
                VALUES ('edge_deleted', 'edge', OLD.id, to_jsonb(OLD));
                RETURN OLD;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER trg_edge_events
        AFTER INSERT OR DELETE ON {SCHEMA}.knowledge_edges
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.emit_edge_event();
    """)
    
    # Node versioning trigger
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.save_node_version()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND OLD.version != NEW.version THEN
                INSERT INTO {SCHEMA}.node_versions (
                    node_id, version_number, title, content, tags, 
                    change_type, changed_by, changed_at
                )
                VALUES (
                    OLD.id, OLD.version, OLD.title, OLD.content, OLD.tags,
                    'update', NEW.updated_by, NOW()
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER trg_node_versioning
        BEFORE UPDATE ON {SCHEMA}.knowledge_nodes
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.save_node_version();
    """)
    
    # =========================================================================
    # HYBRID SEARCH FUNCTION
    # =========================================================================
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
    
    # =========================================================================
    # HIT STATISTICS VIEW
    # =========================================================================
    op.execute(f"""
        CREATE OR REPLACE VIEW {SCHEMA}.knowledge_hit_stats AS
        SELECT 
            n.id,
            n.node_type,
            n.title,
            n.tags,
            COUNT(h.id) AS total_hits,
            COUNT(DISTINCT h.session_id) AS unique_sessions,
            COUNT(DISTINCT DATE(h.hit_at)) AS days_with_hits,
            MAX(h.hit_at) AS last_hit_at,
            ROUND(AVG(h.similarity_score)::numeric, 3) AS avg_similarity,
            MODE() WITHIN GROUP (ORDER BY h.retrieval_method) AS primary_retrieval_method
        FROM {SCHEMA}.knowledge_nodes n
        LEFT JOIN {SCHEMA}.knowledge_hits h ON n.id = h.node_id
        WHERE n.is_deleted = FALSE
        GROUP BY n.id, n.node_type, n.title, n.tags;
    """)


def downgrade() -> None:
    op.execute(f"DROP VIEW IF EXISTS {SCHEMA}.knowledge_hit_stats;")
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.hybrid_search_nodes;")
    
    op.execute(f"DROP TRIGGER IF EXISTS trg_node_versioning ON {SCHEMA}.knowledge_nodes;")
    op.execute(f"DROP TRIGGER IF EXISTS trg_edge_events ON {SCHEMA}.knowledge_edges;")
    op.execute(f"DROP TRIGGER IF EXISTS trg_node_events ON {SCHEMA}.knowledge_nodes;")
    
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.save_node_version();")
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.emit_edge_event();")
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.emit_node_event();")
    
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_hits;")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.node_versions;")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.graph_events;")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.staging_nodes;")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_edges;")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_nodes;")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.user_tenant_access;")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.tenants;")
    
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
    op.execute("DROP EXTENSION IF EXISTS vector;")
