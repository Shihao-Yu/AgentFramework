"""
Ticket Pipeline Job

Entry point for running the ticket-to-knowledge pipeline.
Can be run as a scheduled job or manually triggered.

Usage:
    # Run as script
    python -m jobs.ticket_pipeline_job --batch-size 50 --dry-run
    
    # Or import and call
    from jobs.ticket_pipeline_job import run_pipeline
    asyncio.run(run_pipeline(batch_size=50))
"""

import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.core.database import get_session_context
from app.core.dependencies import (
    get_embedding_client_instance,
    get_inference_client_instance,
)
from pipeline.models import TicketData, PipelineConfig, PipelineStats
from pipeline.service import TicketPipeline


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TicketSource:
    """
    Abstract ticket source.
    
    TODO: Implement your actual ticket source (ClickHouse, API, etc.)
    """
    
    async def fetch_tickets(
        self,
        limit: int = 100,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[TicketData]:
        """
        Fetch tickets from source.
        
        Override this method with your actual implementation.
        """
        # Placeholder - returns empty list
        # In production, this would query your ticket database
        logger.warning("TicketSource.fetch_tickets is not implemented")
        return []


class MockTicketSource(TicketSource):
    """Mock ticket source for testing."""
    
    async def fetch_tickets(
        self,
        limit: int = 100,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[TicketData]:
        """Return mock tickets for testing."""
        
        return [
            TicketData(
                ticket_id="TICKET-001",
                subject="How do I reset my password?",
                body="Customer is asking how to reset their password. They forgot it and can't log in.",
                resolution="Directed customer to the 'Forgot Password' link on the login page. They need to click it, enter their email, and follow the reset link sent to their inbox.",
                closure_notes="Password reset successful. Customer confirmed they could log in.",
                created_at=datetime.utcnow() - timedelta(days=1),
                resolved_at=datetime.utcnow(),
                category="Account",
                subcategory="Password",
                tags=["password", "login", "reset"],
                source="mock"
            ),
            TicketData(
                ticket_id="TICKET-002",
                subject="Can't find my order",
                body="I placed an order last week but I can't find it in my order history.",
                resolution="Order was placed under a different email address. Helped customer locate the order by searching with their order confirmation number.",
                closure_notes="Found order under alternate email. Customer happy.",
                created_at=datetime.utcnow() - timedelta(days=2),
                resolved_at=datetime.utcnow(),
                category="Orders",
                subcategory="Order Status",
                tags=["order", "history", "tracking"],
                source="mock"
            ),
        ]


async def run_pipeline(
    batch_size: int = 50,
    dry_run: bool = False,
    source: Optional[TicketSource] = None,
    since: Optional[datetime] = None,
    config: Optional[PipelineConfig] = None
) -> PipelineStats:
    """
    Run the ticket-to-knowledge pipeline.
    
    Args:
        batch_size: Number of tickets to process in this run
        dry_run: If True, don't persist changes
        source: Ticket source (defaults to placeholder implementation)
        since: Only process tickets created after this time
        config: Pipeline configuration
        
    Returns:
        Statistics about the pipeline run
    """
    
    logger.info(f"Starting pipeline run (batch_size={batch_size}, dry_run={dry_run})")
    
    # Initialize source
    if source is None:
        source = TicketSource()
    
    # Initialize config
    if config is None:
        config = PipelineConfig(dry_run=dry_run)
    
    # Fetch tickets
    logger.info("Fetching tickets...")
    tickets = await source.fetch_tickets(limit=batch_size, since=since)
    logger.info(f"Fetched {len(tickets)} tickets")
    
    if not tickets:
        logger.info("No tickets to process")
        return PipelineStats(
            run_id="empty-run",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            total_tickets=0
        )
    
    # Get database session and clients
    async with get_session_context() as session:
        embedding_client = get_embedding_client_instance()
        inference_client = get_inference_client_instance()
        
        # Initialize pipeline
        pipeline = TicketPipeline(
            session=session,
            embedding_client=embedding_client,
            inference_client=inference_client,
            config=config
        )
        
        # Process batch
        logger.info("Processing tickets...")
        stats = await pipeline.process_batch(tickets)
        
        if dry_run:
            logger.info("Dry run - rolling back changes")
            await session.rollback()
        else:
            logger.info("Committing changes")
            await session.commit()
    
    # Log results
    logger.info(f"Pipeline run completed:")
    logger.info(f"  - Total tickets: {stats.total_tickets}")
    logger.info(f"  - Processed: {stats.processed}")
    logger.info(f"  - Skipped: {stats.skipped}")
    logger.info(f"  - New items: {stats.new_items}")
    logger.info(f"  - Merged items: {stats.merged_items}")
    logger.info(f"  - Variants added: {stats.variants_added}")
    logger.info(f"  - Errors: {stats.errors}")
    logger.info(f"  - Avg confidence: {stats.avg_confidence:.2f}")
    logger.info(f"  - Avg processing time: {stats.avg_processing_time_ms:.0f}ms")
    
    return stats


async def run_pipeline_with_mock():
    """Run pipeline with mock data for testing."""
    
    logger.info("Running pipeline with mock ticket source")
    return await run_pipeline(
        batch_size=10,
        dry_run=True,
        source=MockTicketSource()
    )


def main():
    """CLI entry point."""
    
    parser = argparse.ArgumentParser(
        description="Run the ticket-to-knowledge pipeline"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of tickets to process (default: 50)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't persist changes (for testing)"
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=None,
        help="Only process tickets from the last N days"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock ticket source for testing"
    )
    parser.add_argument(
        "--skip-threshold",
        type=float,
        default=0.95,
        help="Similarity threshold for skipping (default: 0.95)"
    )
    parser.add_argument(
        "--variant-threshold",
        type=float,
        default=0.85,
        help="Similarity threshold for adding variants (default: 0.85)"
    )
    parser.add_argument(
        "--merge-threshold",
        type=float,
        default=0.70,
        help="Similarity threshold for considering merge (default: 0.70)"
    )
    
    args = parser.parse_args()
    
    # Build config
    config = PipelineConfig(
        similarity_skip_threshold=args.skip_threshold,
        similarity_variant_threshold=args.variant_threshold,
        similarity_merge_threshold=args.merge_threshold,
        dry_run=args.dry_run
    )
    
    # Calculate since date
    since = None
    if args.since_days:
        since = datetime.utcnow() - timedelta(days=args.since_days)
    
    # Select source
    source = MockTicketSource() if args.mock else TicketSource()
    
    # Run pipeline
    stats = asyncio.run(run_pipeline(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        source=source,
        since=since,
        config=config
    ))
    
    # Exit with error code if there were errors
    if stats.errors > 0:
        exit(1)


if __name__ == "__main__":
    main()
