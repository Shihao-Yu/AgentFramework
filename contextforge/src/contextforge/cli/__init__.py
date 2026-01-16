"""
ContextForge CLI - Database management and utility commands.

Commands:
    contextforge db init      - Initialize database schema and migrations
    contextforge db upgrade   - Run pending migrations
    contextforge db status    - Show migration status
    contextforge db downgrade - Revert last migration

Usage:
    contextforge --help
    contextforge db upgrade --revision head
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click

from contextforge.core.config import ContextForgeConfig


def run_async(coro):
    """Run async function in sync context."""
    return asyncio.get_event_loop().run_until_complete(coro)


def get_config() -> ContextForgeConfig:
    """Load configuration from environment."""
    return ContextForgeConfig()


@click.group()
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    help="Path to configuration file",
)
@click.option(
    "--database-url",
    envvar="FRAMEWORK_DB_URL",
    help="Database URL (overrides config)",
)
@click.pass_context
def cli(ctx, config_file: Optional[str], framework_db_url: Optional[str]):
    """
    ContextForge CLI - Knowledge management library utilities.
    
    Database operations, schema management, and diagnostics.
    """
    ctx.ensure_object(dict)
    
    # Load config
    if config_file:
        # TODO: Load from file
        config = get_config()
    else:
        config = get_config()
    
    # Override database URL if provided
    if framework_db_url:
        config = ContextForgeConfig(framework_db_url=framework_db_url)
    
    ctx.obj["config"] = config


# ===================
# Database Commands
# ===================

@cli.group()
@click.pass_context
def db(ctx):
    """Database management commands."""
    pass


@db.command("init")
@click.option(
    "--schema",
    "-s",
    default=None,
    help="Database schema name (default: from config db_schema)",
)
@click.pass_context
def db_init(ctx, schema: Optional[str]):
    """
    Initialize database schema and extensions.
    
    Creates:
    - Database schema (if not exists)
    - pgvector extension
    - Required functions (hybrid_search_nodes, etc.)
    """
    config: ContextForgeConfig = ctx.obj["config"]
    schema = schema or config.db_schema
    click.echo(f"Initializing database schema: {schema}")
    
    async def _init():
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        
        # Need sync connection for schema/extension creation
        # Convert async URL to sync URL
        sync_url = config.framework_db_url.replace(
            "postgresql+asyncpg://",
            "postgresql://"
        )
        
        # For schema creation, use psycopg2 directly
        try:
            import psycopg2
            from urllib.parse import urlparse
            
            parsed = urlparse(sync_url)
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                dbname=parsed.path[1:],  # Remove leading /
            )
            conn.autocommit = True
            cur = conn.cursor()
            
            # Create schema
            click.echo(f"  Creating schema '{schema}'...")
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            
            # Create extensions
            click.echo("  Enabling pgvector extension...")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            click.echo("  Enabling pg_trgm extension...")
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            
            cur.close()
            conn.close()
            
            click.echo("\nDatabase initialized successfully!")
            click.echo(f"  Schema: {schema}")
            click.echo("  Extensions: vector, pg_trgm")
            click.echo("\nNext steps:")
            click.echo("  1. Run migrations: contextforge db upgrade")
            
        except ImportError:
            click.echo("Error: psycopg2 not installed. Run: pip install psycopg2-binary", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"Error initializing database: {e}", err=True)
            sys.exit(1)
    
    run_async(_init())


@db.command("upgrade")
@click.option(
    "--revision",
    "-r",
    default="head",
    help="Target revision (default: head)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show SQL without executing",
)
@click.pass_context
def db_upgrade(ctx, revision: str, dry_run: bool):
    """
    Run database migrations.
    
    Applies all pending migrations up to the specified revision.
    
    Examples:
        contextforge db upgrade              # Upgrade to latest
        contextforge db upgrade -r abc123    # Upgrade to specific revision
        contextforge db upgrade --dry-run    # Preview SQL
    """
    config: ContextForgeConfig = ctx.obj["config"]
    click.echo(f"Running migrations to: {revision}")
    
    # Find alembic.ini
    alembic_ini = _find_alembic_ini()
    if not alembic_ini:
        click.echo(
            "Error: alembic.ini not found. "
            "Run from project root or set ALEMBIC_CONFIG.",
            err=True,
        )
        sys.exit(1)
    
    try:
        from alembic.config import Config
        from alembic import command
        
        alembic_cfg = Config(str(alembic_ini))
        
        # Override database URL
        alembic_cfg.set_main_option(
            "sqlalchemy.url",
            config.framework_db_url.replace("+asyncpg", ""),
        )
        
        if dry_run:
            click.echo("\n[DRY RUN] SQL that would be executed:\n")
            command.upgrade(alembic_cfg, revision, sql=True)
        else:
            command.upgrade(alembic_cfg, revision)
            click.echo("\nMigrations applied successfully!")
            
    except ImportError:
        click.echo("Error: alembic not installed. Run: pip install alembic", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error running migrations: {e}", err=True)
        sys.exit(1)


@db.command("downgrade")
@click.option(
    "--revision",
    "-r",
    default="-1",
    help="Target revision (default: -1 for one step back)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show SQL without executing",
)
@click.confirmation_option(
    prompt="This will revert database changes. Continue?",
)
@click.pass_context
def db_downgrade(ctx, revision: str, dry_run: bool):
    """
    Revert database migrations.
    
    Reverts to the specified revision.
    
    Examples:
        contextforge db downgrade            # Revert one step
        contextforge db downgrade -r base    # Revert all migrations
    """
    config: ContextForgeConfig = ctx.obj["config"]
    click.echo(f"Reverting migrations to: {revision}")
    
    alembic_ini = _find_alembic_ini()
    if not alembic_ini:
        click.echo("Error: alembic.ini not found.", err=True)
        sys.exit(1)
    
    try:
        from alembic.config import Config
        from alembic import command
        
        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option(
            "sqlalchemy.url",
            config.framework_db_url.replace("+asyncpg", ""),
        )
        
        if dry_run:
            click.echo("\n[DRY RUN] SQL that would be executed:\n")
            command.downgrade(alembic_cfg, revision, sql=True)
        else:
            command.downgrade(alembic_cfg, revision)
            click.echo("\nMigration reverted successfully!")
            
    except Exception as e:
        click.echo(f"Error reverting migrations: {e}", err=True)
        sys.exit(1)


@db.command("status")
@click.pass_context
def db_status(ctx):
    """
    Show database migration status.
    
    Displays current revision and pending migrations.
    """
    config: ContextForgeConfig = ctx.obj["config"]
    
    alembic_ini = _find_alembic_ini()
    if not alembic_ini:
        click.echo("Error: alembic.ini not found.", err=True)
        sys.exit(1)
    
    try:
        from alembic.config import Config
        from alembic import command
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine
        
        alembic_cfg = Config(str(alembic_ini))
        sync_url = config.framework_db_url.replace("+asyncpg", "")
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        
        # Get current revision
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
        
        # Get head revision
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        
        click.echo("\nDatabase Migration Status")
        click.echo("=" * 40)
        click.echo(f"  Current revision: {current_rev or '(none)'}")
        click.echo(f"  Latest revision:  {head_rev or '(none)'}")
        
        if current_rev == head_rev:
            click.echo("\n  Status: Up to date")
        elif current_rev is None:
            click.echo("\n  Status: No migrations applied")
            click.echo("  Run: contextforge db upgrade")
        else:
            # Count pending migrations
            pending = []
            for rev in script.iterate_revisions(head_rev, current_rev):
                if rev.revision != current_rev:
                    pending.append(rev)
            
            click.echo(f"\n  Status: {len(pending)} pending migration(s)")
            for rev in reversed(pending):
                click.echo(f"    - {rev.revision}: {rev.doc or 'No description'}")
            click.echo("\n  Run: contextforge db upgrade")
            
    except Exception as e:
        click.echo(f"Error checking status: {e}", err=True)
        sys.exit(1)


@db.command("check")
@click.pass_context
def db_check(ctx):
    """
    Check database connection and schema.
    
    Verifies:
    - Database connectivity
    - Required extensions
    - Schema existence
    - Table counts
    """
    config: ContextForgeConfig = ctx.obj["config"]
    click.echo("Checking database...")
    
    async def _check():
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        
        engine = create_async_engine(config.framework_db_url)
        
        try:
            async with engine.connect() as conn:
                # Connection check
                click.echo("\n  Connection: OK")
                
                # Extension check
                result = await conn.execute(text("""
                    SELECT extname FROM pg_extension 
                    WHERE extname IN ('vector', 'pg_trgm')
                """))
                extensions = [row[0] for row in result.fetchall()]
                
                click.echo(f"  Extensions: {', '.join(extensions) if extensions else 'None'}")
                
                if 'vector' not in extensions:
                    click.echo("    WARNING: pgvector not installed!", err=True)
                
                # Schema check
                schema = config.db_schema
                result = await conn.execute(text("""
                    SELECT schema_name FROM information_schema.schemata
                    WHERE schema_name = :schema
                """), {"schema": schema})
                schema_exists = result.fetchone() is not None
                
                click.echo(f"  Schema '{schema}': {'OK' if schema_exists else 'NOT FOUND'}")
                
                if schema_exists:
                    # Table count
                    result = await conn.execute(text("""
                        SELECT COUNT(*) FROM information_schema.tables
                        WHERE table_schema = :schema
                    """), {"schema": schema})
                    table_count = result.scalar()
                    click.echo(f"  Tables: {table_count}")
                    
                    # Row counts for main tables
                    for table in ["knowledge_nodes", "knowledge_edges", "tenants"]:
                        try:
                            result = await conn.execute(
                                text(f"SELECT COUNT(*) FROM {schema}.{table}")
                            )
                            count = result.scalar()
                            click.echo(f"    - {table}: {count} rows")
                        except Exception:
                            pass
                
                click.echo("\nDatabase check complete!")
                
        except Exception as e:
            click.echo(f"\n  Connection: FAILED", err=True)
            click.echo(f"  Error: {e}", err=True)
            sys.exit(1)
        finally:
            await engine.dispose()
    
    run_async(_check())


# ===================
# Info Commands  
# ===================

@cli.command("version")
def version():
    """Show ContextForge version."""
    from contextforge import __version__
    click.echo(f"ContextForge {__version__}")


@cli.command("info")
@click.pass_context
def info(ctx):
    """Show ContextForge configuration and status."""
    config: ContextForgeConfig = ctx.obj["config"]
    
    click.echo("\nContextForge Configuration")
    click.echo("=" * 40)
    click.echo(f"  Database URL: {_mask_password(config.framework_db_url)}")
    click.echo(f"  Schema: {config.db_schema}")
    click.echo(f"  Pool Size: {config.db_pool_size}")
    click.echo("\n  Features:")
    click.echo(f"    - QueryForge: {config.enable_queryforge}")
    click.echo(f"    - Staging: {config.enable_staging}")
    click.echo(f"    - Analytics: {config.enable_analytics}")
    click.echo(f"    - Admin UI: {config.admin_ui_enabled}")
    click.echo("\n  Search Weights:")
    click.echo(f"    - BM25: {config.search_bm25_weight}")
    click.echo(f"    - Vector: {config.search_vector_weight}")


# ===================
# Utilities
# ===================

def _find_alembic_ini() -> Optional[Path]:
    """Find alembic.ini file."""
    # Check environment variable first
    if env_path := os.environ.get("ALEMBIC_CONFIG"):
        path = Path(env_path)
        if path.exists():
            return path
    
    # Search common locations
    search_paths = [
        Path.cwd() / "alembic.ini",
        Path.cwd() / "contextforge" / "alembic.ini",
        Path(__file__).parent.parent.parent / "alembic.ini",
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    
    return None


def _mask_password(url: str) -> str:
    """Mask password in database URL."""
    if "@" not in url:
        return url
    
    # postgresql+asyncpg://user:password@host/db
    try:
        prefix, rest = url.split("://", 1)
        if "@" in rest:
            auth, host_db = rest.rsplit("@", 1)
            if ":" in auth:
                user, _ = auth.split(":", 1)
                return f"{prefix}://{user}:****@{host_db}"
    except Exception:
        pass
    
    return url


def main():
    """CLI entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
