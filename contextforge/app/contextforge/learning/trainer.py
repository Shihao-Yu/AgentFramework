"""
Training Manager for ContextForge.

Manages the collection, validation, and storage of Q&A training examples.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..schema import ExampleSpec

logger = logging.getLogger(__name__)


class ExampleStatus(str, Enum):
    """Status of a training example."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    VALIDATED = "validated"
    REJECTED = "rejected"
    PROMOTED = "promoted"


class ValidationResult(str, Enum):
    """Result of example validation."""
    VALID = "valid"
    INVALID_QUERY = "invalid_query"
    INVALID_QUESTION = "invalid_question"
    DUPLICATE = "duplicate"
    INCOMPLETE = "incomplete"


@dataclass
class ValidationReport:
    """Report from validating an example."""
    result: ValidationResult
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    score: float = 0.0
    
    @property
    def is_valid(self) -> bool:
        return self.result == ValidationResult.VALID


@dataclass
class TrainingStats:
    """Statistics about training examples."""
    total_examples: int = 0
    validated_count: int = 0
    pending_count: int = 0
    rejected_count: int = 0
    promoted_count: int = 0
    avg_quality_score: float = 0.0


class TrainingManager:
    """
    Manages training examples for query generation.
    
    Responsibilities:
    - Collect Q&A examples from various sources
    - Validate examples for quality and correctness
    - Store examples with embeddings for retrieval
    - Track example lifecycle (draft -> validated -> promoted)
    """
    
    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id
    
    async def add_example(
        self,
        session: AsyncSession,
        dataset_name: str,
        question: str,
        query: str,
        explanation: Optional[str] = None,
        source: str = "manual",
        auto_validate: bool = True,
    ) -> ExampleSpec:
        """
        Add a new training example.
        
        Args:
            session: Database session
            dataset_name: Target dataset
            question: Natural language question
            query: Expected query/answer
            explanation: Optional explanation
            source: Source of the example (manual, generated, imported)
            auto_validate: Run validation automatically
            
        Returns:
            Created ExampleSpec
        """
        from ..storage import PostgresVectorAdapter
        
        example = ExampleSpec(
            id=f"{dataset_name}_{hash(question) % 100000}_{int(datetime.utcnow().timestamp())}",
            question=question,
            query=query,
            explanation=explanation or "",
            dataset_name=dataset_name,
            is_validated=False,
            metadata={
                "source": source,
                "status": ExampleStatus.DRAFT.value,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
        
        if auto_validate:
            report = await self.validate_example(session, example)
            if report.is_valid:
                example.is_validated = True
                example.metadata["status"] = ExampleStatus.VALIDATED.value
                example.metadata["quality_score"] = report.score
            else:
                example.metadata["validation_issues"] = report.issues
        
        adapter = PostgresVectorAdapter(tenant_id=self.tenant_id)
        await adapter.store_example(session, dataset_name, example)
        
        logger.info(f"Added example for {dataset_name}: {question[:50]}...")
        return example
    
    async def validate_example(
        self,
        session: AsyncSession,
        example: ExampleSpec,
        check_duplicates: bool = True,
    ) -> ValidationReport:
        """
        Validate a training example.
        
        Checks:
        - Question is not empty and has minimum length
        - Query is not empty and appears syntactically valid
        - No exact duplicate questions exist
        - Question and query are not identical
        """
        issues = []
        suggestions = []
        score = 100.0
        
        if not example.question or len(example.question.strip()) < 5:
            issues.append("Question is too short (min 5 characters)")
            score -= 30
        
        if not example.query or len(example.query.strip()) < 5:
            issues.append("Query is too short (min 5 characters)")
            score -= 30
        
        if example.question and example.query:
            if example.question.lower().strip() == example.query.lower().strip():
                issues.append("Question and query should not be identical")
                score -= 20
        
        if example.query:
            query_lower = example.query.lower().strip()
            valid_starts = ["select", "search", "get", "post", "put", "delete", "{", "[", "source"]
            if not any(query_lower.startswith(s) for s in valid_starts):
                suggestions.append("Query doesn't start with common keywords - verify syntax")
                score -= 10
        
        if example.question:
            if not any(c in example.question for c in "?'\""):
                if len(example.question.split()) < 3:
                    suggestions.append("Question is very short - consider adding more context")
                    score -= 5
        
        if check_duplicates and example.question:
            from ..storage import PostgresVectorAdapter
            adapter = PostgresVectorAdapter(tenant_id=self.tenant_id)
            
            existing = await adapter.get_examples(
                session,
                example.dataset_name,
                limit=100,
            )
            
            question_lower = example.question.lower().strip()
            for ex in existing:
                if ex.question.lower().strip() == question_lower:
                    if ex.id != example.id:
                        issues.append(f"Duplicate question found: {ex.id}")
                        score -= 50
                        break
        
        score = max(0.0, min(100.0, score))
        
        result = ValidationResult.VALID if not issues else (
            ValidationResult.DUPLICATE if any("Duplicate" in i for i in issues) else
            ValidationResult.INVALID_QUESTION if any("Question" in i for i in issues) else
            ValidationResult.INVALID_QUERY if any("Query" in i for i in issues) else
            ValidationResult.INCOMPLETE
        )
        
        return ValidationReport(
            result=result,
            issues=issues,
            suggestions=suggestions,
            score=score,
        )
    
    async def bulk_validate(
        self,
        session: AsyncSession,
        dataset_name: str,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Validate all examples for a dataset.
        
        Returns summary statistics and detailed results.
        """
        from ..storage import PostgresVectorAdapter
        
        adapter = PostgresVectorAdapter(tenant_id=self.tenant_id)
        examples = await adapter.get_examples(session, dataset_name, limit=limit)
        
        results = {
            "total": len(examples),
            "valid": 0,
            "invalid": 0,
            "details": [],
        }
        
        for example in examples:
            report = await self.validate_example(session, example, check_duplicates=True)
            
            if report.is_valid:
                results["valid"] += 1
            else:
                results["invalid"] += 1
            
            results["details"].append({
                "id": example.id,
                "question": example.question[:50],
                "result": report.result.value,
                "score": report.score,
                "issues": report.issues,
            })
        
        return results
    
    async def get_stats(
        self,
        session: AsyncSession,
        dataset_name: Optional[str] = None,
    ) -> TrainingStats:
        """
        Get training statistics.
        
        Args:
            session: Database session
            dataset_name: Optional dataset filter
            
        Returns:
            TrainingStats with counts and averages
        """
        from sqlalchemy import select, func
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        
        stmt = select(func.count(KnowledgeNode.id)).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
        )
        
        if dataset_name:
            stmt = stmt.where(KnowledgeNode.dataset_name == dataset_name)
        
        result = await session.execute(stmt)
        total = result.scalar() or 0
        
        return TrainingStats(
            total_examples=total,
            validated_count=0,
            pending_count=0,
            rejected_count=0,
            promoted_count=0,
            avg_quality_score=0.0,
        )
    
    async def update_example_status(
        self,
        session: AsyncSession,
        example_id: str,
        status: ExampleStatus,
    ) -> bool:
        """
        Update the status of an example.
        
        Args:
            session: Database session
            example_id: Example ID
            status: New status
            
        Returns:
            True if updated successfully
        """
        from sqlalchemy import select, update
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == self.tenant_id,
            KnowledgeNode.node_type == NodeType.EXAMPLE,
            KnowledgeNode.source_reference == example_id,
        )
        
        result = await session.execute(stmt)
        node = result.scalar_one_or_none()
        
        if not node:
            return False
        
        content = node.content
        content["status"] = status.value
        content["status_updated_at"] = datetime.utcnow().isoformat()
        
        node.content = content
        node.updated_at = datetime.utcnow()
        
        await session.flush()
        return True
    
    async def import_examples_from_file(
        self,
        session: AsyncSession,
        dataset_name: str,
        file_content: str,
        format: str = "json",
    ) -> Dict[str, int]:
        """
        Import examples from file content.
        
        Supports JSON format with list of {question, query, explanation} objects.
        
        Returns:
            Dict with import statistics
        """
        import json
        
        results = {"imported": 0, "failed": 0, "skipped": 0}
        
        if format == "json":
            try:
                data = json.loads(file_content)
                if not isinstance(data, list):
                    data = [data]
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                return results
        else:
            logger.error(f"Unsupported format: {format}")
            return results
        
        for item in data:
            question = item.get("question") or item.get("q")
            query = item.get("query") or item.get("answer") or item.get("a")
            explanation = item.get("explanation") or item.get("e")
            
            if not question or not query:
                results["skipped"] += 1
                continue
            
            try:
                await self.add_example(
                    session,
                    dataset_name,
                    question=question,
                    query=query,
                    explanation=explanation,
                    source="import",
                    auto_validate=True,
                )
                results["imported"] += 1
            except Exception as e:
                logger.warning(f"Failed to import example: {e}")
                results["failed"] += 1
        
        return results
