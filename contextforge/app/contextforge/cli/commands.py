"""
CLI Commands for ContextForge.

Provides Click-based commands for:
- Data source onboarding
- Example training and validation
- Schema export
- Prompt sync with Langfuse
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

from ..schema.yaml_schema import SchemaType

DB_SCHEMA = os.environ.get("DB_SCHEMA", "agent")


def run_async(coro):
    """Run async function in sync context."""
    return asyncio.get_event_loop().run_until_complete(coro)


@click.group()
@click.option("--tenant", "-t", default="default", help="Tenant ID")
@click.pass_context
def cli(ctx, tenant: str):
    """ContextForge CLI - Schema onboarding and query generation tools."""
    ctx.ensure_object(dict)
    ctx.obj["tenant_id"] = tenant


@cli.command()
@click.argument("source_type", type=click.Choice(["postgres", "opensearch", "clickhouse", "rest_api"]))
@click.argument("connection_string")
@click.option("--name", "-n", required=True, help="Dataset name")
@click.option("--schema", "-s", help="Schema/index name to import")
@click.option("--output", "-o", type=click.Path(), help="Output YAML file path")
@click.option("--dry-run", is_flag=True, help="Preview without saving")
@click.pass_context
def onboard(
    ctx,
    source_type: str,
    connection_string: str,
    name: str,
    schema: Optional[str],
    output: Optional[str],
    dry_run: bool,
):
    """
    Onboard a new data source.
    
    Connects to the data source, extracts schema, and creates KnowledgeNodes.
    
    Examples:
    
        contextforge onboard postgres "postgresql://user:pass@host/db" -n mydb
        
        contextforge onboard opensearch "https://host:9200" -n logs -s log-*
    """
    click.echo(f"Onboarding {source_type} source: {name}")
    
    async def _onboard():
        from app.core.database import get_session_context as get_async_session
        
        tenant_id = ctx.obj["tenant_id"]
        
        if source_type == "postgres":
            from ..sources.postgres import PostgresSource
            source = PostgresSource(connection_string)
        elif source_type == "opensearch":
            from ..sources.opensearch import OpenSearchSource
            source = OpenSearchSource(connection_string)
        elif source_type == "clickhouse":
            from ..sources.clickhouse import ClickHouseSource
            source = ClickHouseSource(connection_string)
        elif source_type == "rest_api":
            from ..sources.rest_api import RestAPISource
            source = RestAPISource(connection_string)
        else:
            click.echo(f"Unknown source type: {source_type}", err=True)
            return
        
        click.echo("Connecting to source...")
        try:
            await source.connect()
        except Exception as e:
            click.echo(f"Failed to connect: {e}", err=True)
            return
        
        click.echo("Extracting schema...")
        try:
            schema_data = await source.extract_schema(schema_name=schema)
        except Exception as e:
            click.echo(f"Failed to extract schema: {e}", err=True)
            await source.disconnect()
            return
        
        await source.disconnect()
        
        if output:
            output_path = Path(output)
            yaml_content = schema_data.to_yaml() if hasattr(schema_data, "to_yaml") else str(schema_data)
            
            if dry_run:
                click.echo(f"\n[DRY RUN] Would write to {output_path}:\n")
                click.echo(yaml_content[:2000])
                if len(yaml_content) > 2000:
                    click.echo(f"\n... ({len(yaml_content)} chars total)")
            else:
                output_path.write_text(yaml_content)
                click.echo(f"Wrote schema to {output_path}")
        
        if not dry_run:
            async with get_async_session() as session:
                from ..storage import PostgresSchemaAdapter
                
                adapter = PostgresSchemaAdapter(tenant_id=tenant_id)
                
                field_count = 0
                if hasattr(schema_data, "indices"):
                    for index in schema_data.indices:
                        for field in index.fields:
                            await adapter.store_field(session, name, field)
                            field_count += 1
                
                await session.commit()
                click.echo(f"Stored {field_count} fields to database")
        
        click.echo("Onboarding complete!")
    
    run_async(_onboard())


@cli.command()
@click.argument("dataset_name")
@click.option("--question", "-q", required=True, help="Natural language question")
@click.option("--query", "-Q", required=True, help="Expected query/answer")
@click.option("--explanation", "-e", help="Optional explanation")
@click.option("--validate/--no-validate", default=True, help="Validate example before saving")
@click.pass_context
def train(
    ctx,
    dataset_name: str,
    question: str,
    query: str,
    explanation: Optional[str],
    validate: bool,
):
    """
    Add a training example for a dataset.
    
    Examples are used for few-shot learning during query generation.
    
    Example:
    
        contextforge train mydb -q "Show orders from last week" -Q "SELECT * FROM orders WHERE created_at > NOW() - INTERVAL '7 days'"
    """
    click.echo(f"Adding training example for {dataset_name}")
    
    async def _train():
        from app.core.database import get_session_context as get_async_session
        from ..schema import ExampleSpec
        from ..storage import PostgresVectorAdapter
        
        tenant_id = ctx.obj["tenant_id"]
        
        example = ExampleSpec(
            id=f"{dataset_name}_{hash(question) % 10000}",
            question=question,
            query=query,
            explanation=explanation or "",
            dataset_name=dataset_name,
            is_validated=False,
        )
        
        if validate:
            click.echo("Validating example...")
            # Basic validation - check query syntax
            query_lower = query.lower().strip()
            if not any(query_lower.startswith(kw) for kw in ["select", "search", "get", "post", "{"]):
                click.echo("Warning: Query doesn't start with expected keyword", err=True)
        
        async with get_async_session() as session:
            adapter = PostgresVectorAdapter(tenant_id=tenant_id)
            
            await adapter.store_example(session, dataset_name, example)
            await session.commit()
            
            click.echo(f"Added example: {question[:50]}...")
    
    run_async(_train())


@cli.command("validate")
@click.argument("dataset_name")
@click.option("--limit", "-l", default=10, help="Number of examples to validate")
@click.option("--auto-fix", is_flag=True, help="Automatically fix minor issues")
@click.pass_context
def validate_examples(ctx, dataset_name: str, limit: int, auto_fix: bool):
    """
    Validate training examples for a dataset.
    
    Checks examples for:
    - Query syntax validity
    - Field references match schema
    - No duplicate questions
    """
    click.echo(f"Validating examples for {dataset_name}")
    
    async def _validate():
        from app.core.database import get_session_context as get_async_session
        from ..storage import PostgresVectorAdapter
        
        tenant_id = ctx.obj["tenant_id"]
        
        async with get_async_session() as session:
            adapter = PostgresVectorAdapter(tenant_id=tenant_id)
            
            examples = await adapter.get_examples(session, dataset_name, limit=limit)
            
            valid_count = 0
            invalid_count = 0
            
            for example in examples:
                issues = []
                
                if not example.question or len(example.question) < 5:
                    issues.append("Question too short")
                
                if not example.query or len(example.query) < 5:
                    issues.append("Query too short")
                
                if example.question and example.query:
                    if example.question.lower() == example.query.lower():
                        issues.append("Question and query are identical")
                
                if issues:
                    invalid_count += 1
                    click.echo(f"  INVALID: {example.question[:40]}...")
                    for issue in issues:
                        click.echo(f"    - {issue}")
                else:
                    valid_count += 1
            
            click.echo(f"\nValidation complete: {valid_count} valid, {invalid_count} invalid")
    
    run_async(_validate())


@cli.command()
@click.argument("dataset_name")
@click.argument("output_path", type=click.Path())
@click.option("--format", "-f", "fmt", type=click.Choice(["yaml", "json"]), default="yaml")
@click.option("--include-examples", is_flag=True, help="Include training examples")
@click.pass_context
def export(ctx, dataset_name: str, output_path: str, fmt: str, include_examples: bool):
    """
    Export dataset schema to file.
    
    Exports the schema configuration including fields, concepts, and optionally examples.
    
    Example:
    
        contextforge export mydb ./schemas/mydb.yaml --include-examples
    """
    click.echo(f"Exporting {dataset_name} to {output_path}")
    
    async def _export():
        from app.core.database import get_session_context as get_async_session
        from ..storage import PostgresSchemaStore
        
        tenant_id = ctx.obj["tenant_id"]
        
        async with get_async_session() as session:
            store = PostgresSchemaStore(tenant_id=tenant_id)
            
            schema = await store.get_schema(session, dataset_name)
            
            if not schema:
                click.echo(f"Schema not found for {dataset_name}", err=True)
                return
            
            output = Path(output_path)
            
            if fmt == "yaml":
                content = schema.to_yaml() if hasattr(schema, "to_yaml") else str(schema)
            else:
                content = schema.model_dump_json(indent=2) if hasattr(schema, "model_dump_json") else json.dumps(schema, indent=2)
            
            output.write_text(content)
            click.echo(f"Exported to {output_path}")
    
    run_async(_export())


@cli.command("sync-prompts")
@click.option("--direction", "-d", type=click.Choice(["push", "pull"]), default="push")
@click.option("--name", "-n", help="Specific prompt name to sync")
@click.pass_context
def sync_prompts(ctx, direction: str, name: Optional[str]):
    """
    Sync prompts with Langfuse.
    
    Push local prompts to Langfuse or pull from Langfuse to local storage.
    
    Example:
    
        contextforge sync-prompts --direction push
    """
    click.echo(f"Syncing prompts ({direction})")
    
    async def _sync():
        from app.core.database import get_session_context as get_async_session
        from ..prompts import PostgresPromptStore, create_langfuse_sync
        
        tenant_id = ctx.obj["tenant_id"]
        
        async with get_async_session() as session:
            store = PostgresPromptStore(tenant_id=tenant_id)
            sync = create_langfuse_sync(store)
            
            if not sync.is_enabled:
                click.echo("Langfuse sync is not configured. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY.", err=True)
                return
            
            results = await sync.sync_all(session, direction=direction)
            
            click.echo(f"Sync complete: {results['success']} succeeded, {results.get('failed', 0)} failed")
    
    run_async(_sync())


@cli.command()
@click.argument("dataset_name")
@click.argument("question")
@click.option("--dialect", "-d", default="postgres", help="Query dialect")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.pass_context
def generate(ctx, dataset_name: str, question: str, dialect: str, verbose: bool):
    """
    Generate a query from natural language.
    
    Uses the trained schema and examples to generate a query.
    
    Example:
    
        contextforge generate mydb "Show all orders from last month"
    """
    click.echo(f"Generating query for: {question}")
    
    async def _generate():
        from app.core.database import get_session_context as get_async_session
        from app.clients import get_inference_client
        from ..generation import QueryGenerationPipeline
        from ..retrieval import GraphContextRetriever
        
        tenant_id = ctx.obj["tenant_id"]
        
        async with get_async_session() as session:
            retriever = GraphContextRetriever(tenant_id=tenant_id)
            inference_client = get_inference_client()
            
            pipeline = QueryGenerationPipeline(
                retriever=retriever,
                inference_client=inference_client,
                dialect=dialect,
            )
            
            result = await pipeline.generate(session, dataset_name, question)
            
            if verbose:
                click.echo(f"\nContext fields: {result.context_field_count if hasattr(result, 'context_field_count') else 'N/A'}")
                click.echo(f"Examples used: {result.example_count if hasattr(result, 'example_count') else 'N/A'}")
            
            click.echo(f"\nGenerated Query:\n{result.query if hasattr(result, 'query') else result}")
    
    run_async(_generate())


@cli.command()
@click.pass_context
def status(ctx):
    """
    Show ContextForge status and statistics.
    """
    click.echo("ContextForge Status")
    click.echo("=" * 40)
    
    async def _status():
        from app.core.database import get_session_context as get_async_session
        from sqlalchemy import select, func
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        
        tenant_id = ctx.obj["tenant_id"]
        
        async with get_async_session() as session:
            for node_type in [NodeType.SCHEMA_INDEX, NodeType.SCHEMA_FIELD, NodeType.EXAMPLE, NodeType.PROMPT_TEMPLATE]:
                stmt = select(func.count(KnowledgeNode.id)).where(
                    KnowledgeNode.tenant_id == tenant_id,
                    KnowledgeNode.node_type == node_type,
                )
                result = await session.execute(stmt)
                count = result.scalar() or 0
                click.echo(f"  {node_type.value}: {count}")
    
    run_async(_status())


@cli.command("test-retrieval")
@click.argument("dataset_name")
@click.argument("question")
@click.option("--top-k", "-k", default=10, help="Number of results to return")
@click.option("--strategy", "-s", type=click.Choice(["keyword", "hybrid", "vector"]), default="hybrid", help="Retrieval strategy (keyword=BM25 only, hybrid=BM25+Vector, vector=Vector only)")
@click.option("--show-scores", is_flag=True, help="Show relevance scores")
@click.option("--show-examples", is_flag=True, help="Also retrieve matching examples")
@click.pass_context
def test_retrieval(ctx, dataset_name: str, question: str, top_k: int, strategy: str, show_scores: bool, show_examples: bool):
    """
    Test retrieval pipeline for a question.
    
    Shows what fields and examples would be retrieved for a given question,
    without generating a query. Useful for debugging and tuning.
    
    Strategies:
    - keyword: BM25 text search only (works without embeddings)
    - hybrid: BM25 + Vector search combined (requires embeddings)
    - vector: Vector similarity only (requires embeddings)
    
    Example:
    
        contextforge test-retrieval mydb "Show orders from last week" --show-scores
        
        contextforge test-retrieval mydb "Find active users" -k 5 --strategy keyword
        
        contextforge test-retrieval mydb "pending orders" --show-examples
    """
    click.echo(f"Testing retrieval for: {question}")
    click.echo(f"Dataset: {dataset_name}, Strategy: {strategy}, Top-K: {top_k}")
    click.echo("=" * 60)
    
    async def _test_retrieval():
        from app.core.database import get_session_context as get_async_session
        from app.core.dependencies import get_embedding_client_instance
        from app.models.enums import NodeType
        from sqlalchemy import text
        
        tenant_id = ctx.obj["tenant_id"]
        
        async with get_async_session() as session:
            # First check what nodes exist for this dataset
            result = await session.execute(
                text(f"""
                    SELECT id, title, field_path, data_type, content, 
                           embedding IS NOT NULL as has_embedding,
                           search_vector IS NOT NULL as has_search_vector
                    FROM {DB_SCHEMA}.knowledge_nodes 
                    WHERE tenant_id = :tenant_id
                    AND dataset_name = :dataset_name
                    AND node_type = 'schema_field'
                    AND is_deleted = FALSE
                    AND status = 'published'
                """),
                {"tenant_id": tenant_id, "dataset_name": dataset_name}
            )
            fields = result.fetchall()
            
            if not fields:
                click.echo(f"No schema fields found for dataset '{dataset_name}'", err=True)
                click.echo("Run 'contextforge onboard' first to import a schema.", err=True)
                return
            
            # Check embedding availability
            fields_with_embeddings = sum(1 for f in fields if f.has_embedding)
            fields_with_search_vector = sum(1 for f in fields if f.has_search_vector)
            
            click.echo(f"Found {len(fields)} fields in schema")
            click.echo(f"  - With embeddings: {fields_with_embeddings}")
            click.echo(f"  - With search vectors: {fields_with_search_vector}")
            
            # Auto-fallback to keyword if no embeddings
            effective_strategy = strategy
            if strategy in ("hybrid", "vector") and fields_with_embeddings == 0:
                click.echo(f"\n[!] No embeddings available, falling back to keyword-only search")
                effective_strategy = "keyword"
            
            click.echo(f"\nUsing strategy: {effective_strategy}\n")
            
            # Execute search based on strategy
            if effective_strategy == "keyword":
                # BM25 keyword search only
                result = await session.execute(
                    text(f"""
                        SELECT 
                            n.id,
                            n.title,
                            n.field_path,
                            n.data_type,
                            n.content,
                            ts_rank_cd(n.search_vector, plainto_tsquery('english', :query)) as bm25_score
                        FROM {DB_SCHEMA}.knowledge_nodes n
                        WHERE n.tenant_id = :tenant_id
                        AND n.dataset_name = :dataset_name
                        AND n.node_type = 'schema_field'
                        AND n.is_deleted = FALSE
                        AND n.status = 'published'
                        AND (
                            n.search_vector @@ plainto_tsquery('english', :query)
                            OR n.title ILIKE :like_query
                            OR n.field_path ILIKE :like_query
                            OR n.content::text ILIKE :like_query
                        )
                        ORDER BY bm25_score DESC NULLS LAST, n.title
                        LIMIT :limit
                    """),
                    {
                        "tenant_id": tenant_id,
                        "dataset_name": dataset_name,
                        "query": question,
                        "like_query": f"%{question}%",
                        "limit": top_k,
                    }
                )
                rows = result.fetchall()
                
                click.echo("RETRIEVED FIELDS (Keyword/BM25 Search)")
                click.echo("-" * 40)
                
                if not rows:
                    click.echo("  (no fields matched)")
                else:
                    for i, row in enumerate(rows, 1):
                        field_name = row.field_path or row.title
                        click.echo(f"  {i}. {field_name}")
                        click.echo(f"     Type: {row.data_type or 'unknown'}")
                        if show_scores:
                            click.echo(f"     BM25 Score: {row.bm25_score or 0:.4f}")
                        if row.content:
                            desc = row.content.get("description", "")
                            if desc:
                                desc = desc[:60] + "..." if len(desc) > 60 else desc
                                click.echo(f"     Desc: {desc}")
                            biz = row.content.get("business_meaning", "")
                            if biz:
                                biz = biz[:60] + "..." if len(biz) > 60 else biz
                                click.echo(f"     Business: {biz}")
                
            else:
                # Hybrid or Vector search using hybrid_search_nodes function
                embedding_client = get_embedding_client_instance()
                query_embedding = await embedding_client.embed(question)
                
                # Set weights based on strategy
                if effective_strategy == "vector":
                    bm25_weight, vector_weight = 0.0, 1.0
                else:  # hybrid
                    bm25_weight, vector_weight = 0.4, 0.6
                
                result = await session.execute(
                    text("""
                        SELECT * FROM agent.hybrid_search_nodes(
                            :query_text,
                            :query_embedding,
                            :tenant_ids,
                            :node_types,
                            NULL,
                            :bm25_weight,
                            :vector_weight,
                            :result_limit
                        )
                        WHERE dataset_name = :dataset_name
                    """),
                    {
                        "query_text": question,
                        "query_embedding": query_embedding,
                        "tenant_ids": [tenant_id],
                        "node_types": [NodeType.SCHEMA_FIELD.value],
                        "bm25_weight": bm25_weight,
                        "vector_weight": vector_weight,
                        "result_limit": top_k,
                        "dataset_name": dataset_name,
                    }
                )
                rows = result.fetchall()
                
                strategy_label = "Vector Only" if effective_strategy == "vector" else "Hybrid (BM25 + Vector)"
                click.echo(f"RETRIEVED FIELDS ({strategy_label})")
                click.echo("-" * 40)
                
                if not rows:
                    click.echo("  (no fields matched)")
                else:
                    for i, row in enumerate(rows, 1):
                        field_name = row.field_path or row.title
                        click.echo(f"  {i}. {field_name}")
                        click.echo(f"     Type: {row.content.get('data_type', 'unknown') if row.content else 'unknown'}")
                        if show_scores:
                            click.echo(f"     BM25: {row.bm25_score:.4f}, Vector: {row.vector_score:.4f}, RRF: {row.rrf_score:.4f}")
                        if row.content:
                            desc = row.content.get("description", "")
                            if desc:
                                desc = desc[:60] + "..." if len(desc) > 60 else desc
                                click.echo(f"     Desc: {desc}")
            
            # Show examples if requested
            if show_examples:
                click.echo(f"\nMATCHING EXAMPLES")
                click.echo("-" * 40)
                
                # Use keyword search for examples too
                result = await session.execute(
                    text(f"""
                        SELECT 
                            n.id,
                            n.title,
                            n.content,
                            ts_rank_cd(n.search_vector, plainto_tsquery('english', :query)) as score
                        FROM {DB_SCHEMA}.knowledge_nodes n
                        WHERE n.tenant_id = :tenant_id
                        AND n.dataset_name = :dataset_name
                        AND n.node_type = 'example'
                        AND n.is_deleted = FALSE
                        AND n.status = 'published'
                        AND (
                            n.search_vector @@ plainto_tsquery('english', :query)
                            OR n.title ILIKE :like_query
                            OR n.content::text ILIKE :like_query
                        )
                        ORDER BY score DESC NULLS LAST
                        LIMIT 5
                    """),
                    {
                        "tenant_id": tenant_id,
                        "dataset_name": dataset_name,
                        "query": question,
                        "like_query": f"%{question}%",
                    }
                )
                examples = result.fetchall()
                
                if examples:
                    for i, ex in enumerate(examples, 1):
                        q = ex.title[:50] + "..." if len(ex.title) > 50 else ex.title
                        click.echo(f"  {i}. Q: {q}")
                        if ex.content:
                            query_str = ex.content.get("query", "")
                            if query_str:
                                query_preview = query_str[:60] + "..." if len(query_str) > 60 else query_str
                                click.echo(f"     A: {query_preview}")
                            verified = ex.content.get("verified", False)
                            click.echo(f"     Verified: {verified}")
                        if show_scores and ex.score:
                            click.echo(f"     Score: {ex.score:.4f}")
                else:
                    click.echo("  (no examples matched)")
            
            # Summary statistics
            click.echo(f"\nSUMMARY")
            click.echo("-" * 40)
            click.echo(f"  Total fields in schema: {len(fields)}")
            click.echo(f"  Strategy used: {effective_strategy}")
            if effective_strategy != strategy:
                click.echo(f"  (requested: {strategy}, fallback due to missing embeddings)")
    
    run_async(_test_retrieval())


def main():
    """CLI entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
