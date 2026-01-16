"""Rename user_id to email in user_tenant_access table.

Revision ID: 007
Revises: 006
Create Date: 2025-01-15

"""
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

SCHEMA = "faq"


def upgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.idx_user_tenant_user;")
    
    op.execute(f"""
        ALTER TABLE {SCHEMA}.user_tenant_access 
        DROP CONSTRAINT user_tenant_access_pkey;
    """)
    
    op.execute(f"""
        ALTER TABLE {SCHEMA}.user_tenant_access 
        RENAME COLUMN user_id TO email;
    """)
    
    op.execute(f"""
        ALTER TABLE {SCHEMA}.user_tenant_access 
        ALTER COLUMN email TYPE VARCHAR(255);
    """)
    
    op.execute(f"""
        ALTER TABLE {SCHEMA}.user_tenant_access 
        ALTER COLUMN granted_by TYPE VARCHAR(255);
    """)
    
    op.execute(f"""
        ALTER TABLE {SCHEMA}.user_tenant_access 
        ADD PRIMARY KEY (email, tenant_id);
    """)
    
    op.execute(f"""
        CREATE INDEX idx_user_tenant_email 
        ON {SCHEMA}.user_tenant_access(email);
    """)


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.idx_user_tenant_email;")
    
    op.execute(f"""
        ALTER TABLE {SCHEMA}.user_tenant_access 
        DROP CONSTRAINT user_tenant_access_pkey;
    """)
    
    op.execute(f"""
        ALTER TABLE {SCHEMA}.user_tenant_access 
        RENAME COLUMN email TO user_id;
    """)
    
    op.execute(f"""
        ALTER TABLE {SCHEMA}.user_tenant_access 
        ALTER COLUMN user_id TYPE VARCHAR(100);
    """)
    
    op.execute(f"""
        ALTER TABLE {SCHEMA}.user_tenant_access 
        ALTER COLUMN granted_by TYPE VARCHAR(100);
    """)
    
    op.execute(f"""
        ALTER TABLE {SCHEMA}.user_tenant_access 
        ADD PRIMARY KEY (user_id, tenant_id);
    """)
    
    op.execute(f"""
        CREATE INDEX idx_user_tenant_user 
        ON {SCHEMA}.user_tenant_access(user_id);
    """)
