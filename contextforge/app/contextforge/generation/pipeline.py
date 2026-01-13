"""
Query generation pipeline with multi-dialect support.

Handles:
- Context retrieval (schema fields, Q&A examples)
- Prompt assembly from templates
- LLM query generation
- Dialect-aware formatting and validation
- Confidence scoring based on retrieval quality

NOTE: This is a simplified version adapted for ContextForge.
The full version will be implemented after retrieval and storage layers are complete.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..core.models import (
    QueryExecutionRecord,
    QueryGenerationResult,
    QueryType,
)
from ..schema.field_schema import FieldSpec
from ..retrieval.context import RetrievalContext
from .strategies import get_strategy

logger = logging.getLogger(__name__)


def calculate_confidence(
    context: RetrievalContext,
    top_k: int = 5,
    field_weight: float = 0.60,
    example_weight: float = 0.25,
    concept_weight: float = 0.15,
) -> float:
    """
    Calculate generation confidence based on retrieval quality.

    Confidence is computed from:
    - Average of top-k field scores (how well schema matches question)
    - Number of examples found (max 3 for full score)
    - Concept coverage (how many concepts were matched)

    Args:
        context: RetrievalContext from retriever
        top_k: Number of top fields to consider for scoring
        field_weight: Weight for field score component
        example_weight: Weight for example component
        concept_weight: Weight for concept component

    Returns:
        Confidence score between 0.0 and 1.0
    """
    # Field confidence: average of top-k scores
    if context.field_scores:
        sorted_scores = sorted(context.field_scores.values(), reverse=True)
        top_scores = sorted_scores[:top_k]
        field_confidence = sum(top_scores) / len(top_scores) if top_scores else 0.0
    else:
        field_confidence = 0.5  # Default if no scores available

    # Example confidence: saturates at 3 examples
    example_count = len(context.examples) if context.examples else 0
    example_confidence = min(1.0, example_count / 3.0)

    # Concept confidence: saturates at 3 concepts
    concept_count = context.expansion_stats.get("concept_count", 0)
    concept_confidence = min(1.0, concept_count / 3.0)

    # Weighted combination
    confidence = (
        field_weight * field_confidence
        + example_weight * example_confidence
        + concept_weight * concept_confidence
    )

    # Clamp to [0.1, 1.0] - never return 0 confidence
    return max(0.1, min(1.0, confidence))


class QueryGenerationPipeline:
    """
    Multi-tenant query generation with dialect awareness.

    This pipeline handles:
    - Context retrieval (fields, examples)
    - Prompt assembly
    - LLM query generation
    - Validation and formatting

    Example:
        >>> pipeline = QueryGenerationPipeline(
        ...     llm_client=llm_client,
        ...     retriever=retriever,
        ... )
        >>>
        >>> result = await pipeline.generate_query(
        ...     tenant_id="acme",
        ...     document_name="orders",
        ...     user_question="Show pending orders",
        ... )
        >>> print(result.query)
        >>> print(f"Confidence: {result.confidence:.2f}")
    """

    def __init__(
        self,
        llm_client: Any,
        retriever: Optional[Any] = None,
        prompt_manager: Optional[Any] = None,
        schema_store: Optional[Any] = None,
        track_usage: bool = True,
    ):
        """
        Initialize query generation pipeline.

        Args:
            llm_client: LLM client with submit_prompt method
            retriever: Context retriever for fields and examples
            prompt_manager: PromptManager for Langfuse integration (optional)
            schema_store: SchemaStore for loading versioned schemas (optional)
            track_usage: Enable usage tracking (default: True)
        """
        self.llm_client = llm_client
        self.retriever = retriever
        self.prompt_manager = prompt_manager
        self.schema_store = schema_store
        self.track_usage = track_usage

    async def generate_query(
        self,
        tenant_id: str,
        document_name: str,
        user_question: str,
        query_type: QueryType = QueryType.POSTGRES,
        run_query_func: Optional[Callable] = None,
        max_correction_retries: int = 3,
        llm_context_threshold: float = 0.6,
    ) -> QueryGenerationResult:
        """
        Generate query from natural language question.

        Args:
            tenant_id: Tenant identifier
            document_name: Document name (dataset)
            user_question: User's natural language question
            query_type: Target query type (postgres, opensearch, etc.)
            run_query_func: Optional function to execute queries
            max_correction_retries: Max retries when query execution fails
            llm_context_threshold: Minimum field score to include in LLM context

        Returns:
            QueryGenerationResult with generated query and confidence
        """
        logger.info(
            f"Generating query for {tenant_id}/{document_name}: {user_question[:50]}..."
        )

        # Track assumptions
        assumptions: List[str] = []

        # Step 1: Retrieve context (if retriever available)
        if self.retriever:
            retrieval_context = await self._retrieve_context(
                tenant_id=tenant_id,
                document_name=document_name,
                question=user_question,
                threshold=llm_context_threshold,
            )
        else:
            # Create minimal context
            retrieval_context = RetrievalContext(
                fields=[],
                expanded_fields=[],
                examples=[],
                documentation=[],
                field_adjacency={},
                expansion_stats={},
            )
            assumptions.append("No retriever configured - using minimal context")

        # Step 2: Calculate confidence from retrieval quality
        confidence = calculate_confidence(retrieval_context)

        # Step 3: Assemble prompt
        assembled_prompt = self._build_prompt(
            context=retrieval_context,
            user_question=user_question,
            query_type=query_type,
        )

        # Step 4: Generate Query via LLM
        generated_query = self.llm_client.submit_prompt(
            [
                self.llm_client.system_message(
                    f"You are an expert {query_type.value} query generator."
                ),
                self.llm_client.user_message(assembled_prompt),
            ]
        )

        # Step 5: Extract & Validate using strategy pattern
        strategy = get_strategy(query_type)
        extracted_query = strategy.extract_query(generated_query)
        validated_query = strategy.format_query(extracted_query)

        if not strategy.is_valid(validated_query):
            logger.warning(f"Query validation failed: {validated_query[:100]}...")
            confidence *= 0.8  # Reduce confidence for invalid queries

        # Step 6: Auto-correction retry loop (if run_query_func provided)
        if run_query_func is not None and max_correction_retries > 0:
            validated_query = await self._retry_with_correction(
                validated_query=validated_query,
                assembled_prompt=assembled_prompt,
                query_type=query_type,
                strategy=strategy,
                run_query_func=run_query_func,
                max_retries=max_correction_retries,
            )

        logger.info(
            f"Query generation completed (confidence={confidence:.2f}, "
            f"fields={retrieval_context.field_count}, "
            f"examples={retrieval_context.example_count})"
        )

        return QueryGenerationResult(
            query=validated_query,
            confidence=confidence,
            context_used={
                "schema_fields": retrieval_context.field_count,
                "examples": retrieval_context.example_count,
                "expanded_fields": retrieval_context.expansion_stats.get(
                    "expanded_count", 0
                ),
            },
            assumptions=assumptions,
        )

    async def _retrieve_context(
        self,
        tenant_id: str,
        document_name: str,
        question: str,
        threshold: float = 0.6,
    ) -> RetrievalContext:
        """Retrieve context using configured retriever."""
        try:
            # The retriever interface will be defined by the retrieval layer
            context = self.retriever.retrieve(
                question=question,
                tenant_id=tenant_id,
                document_name=document_name,
            )
            return context
        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")
            return RetrievalContext(
                fields=[],
                expanded_fields=[],
                examples=[],
                documentation=[],
                field_adjacency={},
                expansion_stats={},
            )

    def _build_prompt(
        self,
        context: RetrievalContext,
        user_question: str,
        query_type: QueryType,
    ) -> str:
        """Build the generation prompt from context."""
        # Format schema fields
        fields_section = self._format_schema_fields(context.all_fields, context)

        # Format examples
        examples_section = self._format_qa_examples(context.examples)

        # Format documentation
        doc_section = self._format_documentation(context.documentation)

        # Assemble prompt
        prompt = f"""Generate a {query_type.value} query for the following question:

Question: {user_question}

{fields_section}

{examples_section}

{doc_section}

Generate ONLY the query without explanation."""

        return prompt

    def _format_schema_fields(
        self,
        fields: List[FieldSpec],
        context: Optional[RetrievalContext] = None,
    ) -> str:
        """Format schema fields for prompt."""
        if not fields:
            return "No relevant schema fields found."

        lines = ["Relevant Schema Fields:"]
        for f in fields:
            qualified = f.qualified_name or f.name

            # Add score if available
            score_str = ""
            if context and context.field_scores:
                score = context.field_scores.get(qualified, 0.0)
                if score > 0:
                    score_str = f" [score: {score:.2f}]"

            lines.append(f"\n- {qualified} ({f.type}){score_str}")
            if f.description:
                lines.append(f"  Description: {f.description}")
            if f.business_meaning:
                lines.append(f"  Business meaning: {f.business_meaning}")
            if f.allowed_values:
                values_display = f.allowed_values[:5]
                if len(f.allowed_values) > 5:
                    values_display.append(f"... ({len(f.allowed_values)} total)")
                lines.append(f"  Allowed values: {', '.join(values_display)}")
            if f.value_encoding:
                encoding_strs = [
                    f"{k}={v}" for k, v in list(f.value_encoding.items())[:5]
                ]
                if len(f.value_encoding) > 5:
                    encoding_strs.append(f"... (+{len(f.value_encoding) - 5})")
                lines.append(f"  Value meanings: {', '.join(encoding_strs)}")

        return "\n".join(lines)

    def _format_qa_examples(self, examples: List[Any]) -> str:
        """Format Q&A examples for prompt."""
        if not examples:
            return "No similar examples found."

        lines = ["Similar Examples:"]
        for i, example in enumerate(examples[:5], 1):
            # Handle different example formats
            if hasattr(example, "title") and hasattr(example, "content"):
                lines.append(f"\n{i}. Question: {example.title}")
                if example.content:
                    lines.append(f"   Query: {example.content.query}")
            elif hasattr(example, "question") and hasattr(example, "query"):
                lines.append(f"\n{i}. Question: {example.question}")
                lines.append(f"   Query: {example.query}")

        return "\n".join(lines)

    def _format_documentation(self, doc_list: List[str]) -> str:
        """Format documentation for prompt."""
        if not doc_list:
            return ""

        lines = ["Documentation:"]
        for i, doc in enumerate(doc_list[:5], 1):
            lines.append(f"\n{i}. {doc}")

        return "\n".join(lines)

    async def _retry_with_correction(
        self,
        validated_query: str,
        assembled_prompt: str,
        query_type: QueryType,
        strategy: Any,
        run_query_func: Callable,
        max_retries: int,
    ) -> str:
        """Retry query generation with error correction."""
        for attempt in range(max_retries):
            try:
                run_query_func(validated_query)
                logger.info(f"Query execution succeeded on attempt {attempt + 1}")
                return validated_query
            except Exception as exec_error:
                if attempt == max_retries - 1:
                    logger.warning(
                        f"Query failed after {max_retries} attempts: {exec_error}"
                    )
                    return validated_query

                error_context = f"""
PREVIOUS QUERY FAILED:
Query: {validated_query}
Error: {exec_error}

Please generate a corrected query that fixes this error.
"""
                retry_prompt = f"{assembled_prompt}\n{error_context}"

                logger.info(
                    f"Attempt {attempt + 1} failed, regenerating with error context..."
                )

                retry_response = self.llm_client.submit_prompt(
                    [
                        self.llm_client.system_message(
                            f"You are an expert {query_type.value} query generator. "
                            "Fix the error in the previous query."
                        ),
                        self.llm_client.user_message(retry_prompt),
                    ]
                )

                extracted_query = strategy.extract_query(retry_response)
                validated_query = strategy.format_query(extracted_query)

        return validated_query
