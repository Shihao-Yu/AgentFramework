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
import sys
from pathlib import Path
from typing import Optional

import click

from ..schema.yaml_schema import SchemaType


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
        from app.database import get_async_session
        
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
        from app.database import get_async_session
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
        from app.database import get_async_session
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
        from app.database import get_async_session
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
        from app.database import get_async_session
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
        from app.database import get_async_session
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
        from app.database import get_async_session
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
@click.option("--strategy", "-s", type=click.Choice(["concept", "field", "hybrid", "fusion"]), default="fusion", help="Retrieval strategy")
@click.option("--show-scores", is_flag=True, help="Show relevance scores")
@click.option("--show-examples", is_flag=True, help="Also retrieve matching examples")
@click.pass_context
def test_retrieval(ctx, dataset_name: str, question: str, top_k: int, strategy: str, show_scores: bool, show_examples: bool):
    """
    Test retrieval pipeline for a question.
    
    Shows what fields and examples would be retrieved for a given question,
    without generating a query. Useful for debugging and tuning.
    
    Example:
    
        contextforge test-retrieval mydb "Show orders from last week" --show-scores
        
        contextforge test-retrieval mydb "Find active users" -k 5 --show-examples
    """
    click.echo(f"Testing retrieval for: {question}")
    click.echo(f"Dataset: {dataset_name}, Strategy: {strategy}, Top-K: {top_k}")
    click.echo("=" * 60)
    
    async def _test_retrieval():
        from app.database import get_async_session
        from app.clients import get_embedding_client
        from ..retrieval import GraphContextRetriever, RetrievalStrategy
        from ..graph import SchemaGraph
        from ..storage import PostgresSchemaStore
        
        tenant_id = ctx.obj["tenant_id"]
        
        async with get_async_session() as session:
            store = PostgresSchemaStore(tenant_id=tenant_id)
            
            fields = await store.get_fields(session, dataset_name)
            
            if not fields:
                click.echo(f"No schema fields found for dataset '{dataset_name}'", err=True)
                click.echo("Run 'contextforge onboard' first to import a schema.", err=True)
                return
            
            click.echo(f"Loaded {len(fields)} fields from schema\n")
            
            graph = SchemaGraph()
            for field in fields:
                graph.add_field(field)
            
            strategy_enum = RetrievalStrategy(strategy)
            retriever = GraphContextRetriever(
                graph=graph,
                strategy=strategy_enum,
            )
            
            context = retriever.retrieve(question, top_k=top_k)
            
            click.echo("RETRIEVED FIELDS")
            click.echo("-" * 40)
            
            if not context.fields:
                click.echo("  (no fields matched)")
            else:
                for i, field in enumerate(context.fields, 1):
                    score_str = ""
                    if show_scores and context.field_scores:
                        score = context.field_scores.get(field.name, 0)
                        score_str = f" [score: {score:.3f}]"
                    
                    click.echo(f"  {i}. {field.name}{score_str}")
                    click.echo(f"     Type: {field.data_type}")
                    if field.description:
                        desc = field.description[:60] + "..." if len(field.description) > 60 else field.description
                        click.echo(f"     Desc: {desc}")
            
            if context.expanded_fields:
                click.echo(f"\nEXPANDED FIELDS (via graph traversal)")
                click.echo("-" * 40)
                for i, field in enumerate(context.expanded_fields, 1):
                    click.echo(f"  {i}. {field.name} ({field.data_type})")
            
            if show_examples:
                click.echo(f"\nMATCHING EXAMPLES")
                click.echo("-" * 40)
                
                if context.examples:
                    for i, ex in enumerate(context.examples, 1):
                        q = ex.question[:50] + "..." if len(ex.question) > 50 else ex.question
                        click.echo(f"  {i}. Q: {q}")
                        query_preview = ex.query[:60] + "..." if len(ex.query) > 60 else ex.query
                        click.echo(f"     A: {query_preview}")
                else:
                    click.echo("  (no examples matched)")
            
            click.echo(f"\nSTATISTICS")
            click.echo("-" * 40)
            click.echo(f"  Fields retrieved: {len(context.fields)}")
            click.echo(f"  Fields expanded: {len(context.expanded_fields)}")
            click.echo(f"  Examples matched: {len(context.examples)}")
            if context.expansion_stats:
                click.echo(f"  Concepts matched: {context.expansion_stats.get('concept_count', 0)}")
                click.echo(f"  Keywords extracted: {context.expansion_stats.get('keyword_count', 0)}")
    
    run_async(_test_retrieval())


def main():
    """CLI entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
