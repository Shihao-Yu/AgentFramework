"""
Ticket-to-Knowledge Pipeline Service.

This service orchestrates the process of converting support tickets
into knowledge base entries.
"""

import json
import time
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.staging import StagingKnowledgeItem
from app.models.knowledge import KnowledgeVariant
from app.models.enums import KnowledgeType, StagingStatus, StagingAction
from app.clients.embedding_client import EmbeddingClient
from app.clients.inference_client import InferenceClient
from app.services.search_service import SearchService

from pipeline.models import (
    TicketData,
    AnalysisResult,
    SimilarItem,
    PipelineResult,
    PipelineStats,
    PipelineConfig,
    PipelineDecision,
)
from pipeline.prompts import (
    build_ticket_analysis_prompt,
    build_merge_decision_prompt,
)


class TicketPipeline:
    """
    Pipeline for converting support tickets to knowledge base entries.
    
    The pipeline follows this decision flow:
    1. Filter: Skip tickets that don't meet basic criteria
    2. Analyze: Use LLM to extract knowledge from ticket
    3. Search: Find similar existing knowledge items
    4. Decide: Based on similarity, decide action:
       - >= 0.95: SKIP (near duplicate)
       - >= 0.85: ADD_VARIANT or SKIP (check if adds info)
       - >= 0.70: LLM decides MERGE vs NEW
       - < 0.70: NEW
    5. Execute: Create staging item or add variant
    """
    
    def __init__(
        self,
        session: AsyncSession,
        embedding_client: EmbeddingClient,
        inference_client: InferenceClient,
        config: Optional[PipelineConfig] = None
    ):
        self.session = session
        self.embedding_client = embedding_client
        self.inference_client = inference_client
        self.config = config or PipelineConfig()
        self.search_service = SearchService(session, embedding_client)
    
    async def process_ticket(self, ticket: TicketData) -> PipelineResult:
        """Process a single ticket through the pipeline."""
        
        start_time = time.time()
        result = PipelineResult(
            ticket_id=ticket.ticket_id,
            decision=PipelineDecision.SKIP
        )
        
        try:
            # Step 1: Filter check
            if not self._passes_filter(ticket):
                result.skipped_reason = "Did not meet minimum criteria"
                return result
            
            # Step 2: Analyze with LLM
            analysis = await self._analyze_ticket(ticket)
            result.analysis = analysis
            
            if not analysis.is_actionable:
                result.decision = PipelineDecision.SKIP
                result.skipped_reason = analysis.quality_notes or "Not actionable"
                return result
            
            if analysis.confidence < self.config.confidence_threshold:
                result.decision = PipelineDecision.SKIP
                result.skipped_reason = f"Low confidence: {analysis.confidence:.2f}"
                return result
            
            # Step 3: Find similar items
            similar_items = await self._find_similar_items(analysis)
            result.similar_items = similar_items
            
            if similar_items:
                result.top_similarity = similar_items[0].similarity
            
            # Step 4: Decide action
            decision, target_id, reasoning = await self._decide_action(
                analysis, similar_items
            )
            result.decision = decision
            
            if decision == PipelineDecision.SKIP:
                result.skipped_reason = reasoning
                return result
            
            # Step 5: Execute action
            if decision == PipelineDecision.ADD_VARIANT:
                result.variant_id = await self._add_variant(
                    target_id, analysis, ticket
                )
            else:
                # NEW or MERGE - create staging item
                result.staging_id = await self._create_staging_item(
                    analysis, ticket, decision, target_id, reasoning
                )
            
            await self.session.commit()
            
        except Exception as e:
            result.error = str(e)
            result.decision = PipelineDecision.SKIP
            result.skipped_reason = f"Error: {str(e)}"
        
        finally:
            result.processing_time_ms = int((time.time() - start_time) * 1000)
        
        return result
    
    async def process_batch(
        self,
        tickets: List[TicketData],
        run_id: Optional[str] = None
    ) -> PipelineStats:
        """Process a batch of tickets."""
        
        stats = PipelineStats(
            run_id=run_id or str(uuid.uuid4()),
            started_at=datetime.utcnow(),
            total_tickets=len(tickets)
        )
        
        confidences = []
        similarities = []
        processing_times = []
        
        for ticket in tickets:
            result = await self.process_ticket(ticket)
            stats.processed += 1
            
            if result.decision == PipelineDecision.SKIP:
                stats.skipped += 1
            elif result.decision == PipelineDecision.NEW:
                stats.new_items += 1
            elif result.decision == PipelineDecision.MERGE:
                stats.merged_items += 1
            elif result.decision == PipelineDecision.ADD_VARIANT:
                stats.variants_added += 1
            
            if result.error:
                stats.errors += 1
            
            if result.analysis and result.analysis.confidence:
                confidences.append(result.analysis.confidence)
            
            if result.top_similarity:
                similarities.append(result.top_similarity)
            
            if result.processing_time_ms:
                processing_times.append(result.processing_time_ms)
        
        stats.completed_at = datetime.utcnow()
        
        if confidences:
            stats.avg_confidence = sum(confidences) / len(confidences)
        if similarities:
            stats.avg_similarity = sum(similarities) / len(similarities)
        if processing_times:
            stats.avg_processing_time_ms = sum(processing_times) / len(processing_times)
        
        return stats
    
    def _passes_filter(self, ticket: TicketData) -> bool:
        """Check if ticket meets minimum criteria for processing."""
        
        # Must have body
        if not ticket.body or len(ticket.body) < self.config.min_body_length:
            return False
        
        # Must have resolution or closure notes
        has_resolution = (
            ticket.resolution and 
            len(ticket.resolution) >= self.config.min_resolution_length
        )
        has_closure_notes = (
            ticket.closure_notes and 
            len(ticket.closure_notes) >= self.config.min_resolution_length
        )
        
        if not has_resolution and not has_closure_notes:
            return False
        
        return True
    
    async def _analyze_ticket(self, ticket: TicketData) -> AnalysisResult:
        """Use LLM to analyze and extract knowledge from ticket."""
        
        prompt = build_ticket_analysis_prompt(
            subject=ticket.subject,
            body=ticket.body,
            resolution=ticket.resolution,
            closure_notes=ticket.closure_notes,
            category=ticket.category,
            tags=ticket.tags
        )
        
        response = await self.inference_client.generate(
            prompt,
            system_prompt="You are a knowledge base curator. Output valid JSON only.",
            temperature=0.3
        )
        
        # Parse LLM response
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError("Failed to parse LLM response as JSON")
        
        return AnalysisResult(
            title=data.get("title", ticket.subject),
            question=data.get("question", ticket.subject),
            answer=data.get("answer", ticket.resolution or ticket.closure_notes or ""),
            summary=data.get("summary"),
            knowledge_type=data.get("knowledge_type", "faq"),
            suggested_tags=data.get("suggested_tags", []),
            confidence=data.get("confidence", 0.5),
            is_actionable=data.get("is_extractable", True),
            quality_notes=data.get("quality_notes")
        )
    
    async def _find_similar_items(
        self,
        analysis: AnalysisResult,
        limit: int = 5
    ) -> List[SimilarItem]:
        """Find similar existing knowledge items."""
        
        # Search using the extracted question
        results = await self.search_service.simple_vector_search(
            query=analysis.question,
            limit=limit,
            knowledge_types=["faq", "troubleshooting", "how_to"]
        )
        
        return [
            SimilarItem(
                id=r["id"],
                title=r["title"],
                content=r["content"],
                knowledge_type=r["knowledge_type"],
                similarity=r["similarity"],
                tags=r.get("tags", [])
            )
            for r in results
        ]
    
    async def _decide_action(
        self,
        analysis: AnalysisResult,
        similar_items: List[SimilarItem]
    ) -> tuple[PipelineDecision, Optional[int], Optional[str]]:
        """
        Decide what action to take based on similarity.
        
        Returns: (decision, target_id, reasoning)
        """
        
        if not similar_items:
            return PipelineDecision.NEW, None, None
        
        top_match = similar_items[0]
        similarity = top_match.similarity
        
        # Very high similarity - likely duplicate
        if similarity >= self.config.similarity_skip_threshold:
            return (
                PipelineDecision.SKIP,
                None,
                f"Near duplicate of item {top_match.id} (similarity: {similarity:.2%})"
            )
        
        # High similarity - add as variant if question is different
        if similarity >= self.config.similarity_variant_threshold:
            if self.config.auto_add_variants:
                # Check if question phrasing is meaningfully different
                existing_question = top_match.content.get("question", top_match.title)
                if self._is_different_phrasing(analysis.question, existing_question):
                    return (
                        PipelineDecision.ADD_VARIANT,
                        top_match.id,
                        f"Adding as variant to item {top_match.id}"
                    )
            
            return (
                PipelineDecision.SKIP,
                None,
                f"Very similar to item {top_match.id} (similarity: {similarity:.2%})"
            )
        
        # Medium similarity - use LLM to decide
        if similarity >= self.config.similarity_merge_threshold:
            decision, reasoning = await self._llm_merge_decision(analysis, top_match)
            
            if decision == "SKIP":
                return PipelineDecision.SKIP, None, reasoning
            elif decision == "ADD_VARIANT":
                return PipelineDecision.ADD_VARIANT, top_match.id, reasoning
            elif decision == "MERGE":
                return PipelineDecision.MERGE, top_match.id, reasoning
            else:
                return PipelineDecision.NEW, None, reasoning
        
        # Low similarity - create new
        return PipelineDecision.NEW, None, None
    
    async def _llm_merge_decision(
        self,
        analysis: AnalysisResult,
        existing: SimilarItem
    ) -> tuple[str, str]:
        """Use LLM to decide between SKIP, ADD_VARIANT, MERGE, or NEW."""
        
        existing_question = existing.content.get("question", existing.title)
        existing_answer = existing.content.get("answer", "")
        
        prompt = build_merge_decision_prompt(
            new_title=analysis.title,
            new_question=analysis.question,
            new_answer=analysis.answer,
            existing_title=existing.title,
            existing_question=existing_question,
            existing_answer=existing_answer,
            similarity=existing.similarity
        )
        
        response = await self.inference_client.generate(
            prompt,
            system_prompt="You are a knowledge base curator. Output valid JSON only.",
            temperature=0.2
        )
        
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                data = json.loads(match.group())
            else:
                return "NEW", "Failed to parse LLM decision"
        
        return data.get("decision", "NEW"), data.get("reasoning", "")
    
    def _is_different_phrasing(self, new_question: str, existing_question: str) -> bool:
        """Check if two questions are different enough to warrant a variant."""
        
        # Simple check: significant word difference
        new_words = set(new_question.lower().split())
        existing_words = set(existing_question.lower().split())
        
        # Remove common words
        common = {"how", "do", "i", "to", "the", "a", "an", "can", "what", "is", "are"}
        new_words -= common
        existing_words -= common
        
        if not new_words or not existing_words:
            return False
        
        # Calculate Jaccard similarity
        intersection = len(new_words & existing_words)
        union = len(new_words | existing_words)
        jaccard = intersection / union if union > 0 else 0
        
        # Different phrasing if Jaccard similarity is below threshold
        return jaccard < 0.7
    
    async def _add_variant(
        self,
        knowledge_item_id: int,
        analysis: AnalysisResult,
        ticket: TicketData
    ) -> int:
        """Add a question variant to an existing knowledge item."""
        
        # Generate embedding
        embedding = await self.embedding_client.embed(analysis.question)
        
        variant = KnowledgeVariant(
            knowledge_item_id=knowledge_item_id,
            variant_text=analysis.question,
            source="pipeline",
            source_reference=ticket.ticket_id,
            created_by="pipeline",
        )
        
        self.session.add(variant)
        await self.session.flush()
        
        # Set embedding
        await self.session.execute(
            text("""
                UPDATE agent.knowledge_variants 
                SET embedding = :embedding::vector 
                WHERE id = :id
            """),
            {"id": variant.id, "embedding": embedding}
        )
        
        return variant.id
    
    async def _create_staging_item(
        self,
        analysis: AnalysisResult,
        ticket: TicketData,
        decision: PipelineDecision,
        merge_target_id: Optional[int],
        merge_reasoning: Optional[str]
    ) -> int:
        """Create a staging item for review."""
        
        # Determine action
        if decision == PipelineDecision.NEW:
            action = StagingAction.NEW
        else:
            action = StagingAction.MERGE
        
        # Map knowledge type
        knowledge_type_map = {
            "faq": KnowledgeType.FAQ,
            "troubleshooting": KnowledgeType.TROUBLESHOOTING,
            "procedure": KnowledgeType.PROCEDURE,
            "business_rule": KnowledgeType.BUSINESS_RULE,
            "how_to": KnowledgeType.FAQ,  # Map how_to to FAQ
        }
        knowledge_type = knowledge_type_map.get(
            analysis.knowledge_type, KnowledgeType.FAQ
        )
        
        # Build content
        content = {
            "question": analysis.question,
            "answer": analysis.answer,
        }
        if analysis.summary:
            content["summary"] = analysis.summary
        
        # Generate embedding
        embed_text = f"{analysis.title}\n{analysis.question}\n{analysis.answer}"
        embedding = await self.embedding_client.embed(embed_text)
        
        staging = StagingKnowledgeItem(
            knowledge_type=knowledge_type,
            title=analysis.title,
            summary=analysis.summary,
            content=content,
            tags=analysis.suggested_tags,
            source_ticket_id=ticket.ticket_id,
            source_type=ticket.source,
            confidence=analysis.confidence,
            status=StagingStatus.PENDING,
            action=action,
            merge_with_id=merge_target_id,
            similarity=ticket.raw_data.get("top_similarity") if ticket.raw_data else None,
            metadata_={
                "ticket_subject": ticket.subject,
                "ticket_category": ticket.category,
                "merge_reasoning": merge_reasoning,
                "processed_at": datetime.utcnow().isoformat(),
            },
            created_by="pipeline",
        )
        
        self.session.add(staging)
        await self.session.flush()
        
        # Set embedding
        await self.session.execute(
            text("""
                UPDATE agent.staging_knowledge_items 
                SET embedding = :embedding::vector 
                WHERE id = :id
            """),
            {"id": staging.id, "embedding": embedding}
        )
        
        return staging.id
