"""
ContextForge Generation Pipeline.

Provides query generation with multi-dialect support:
- QueryGenerationPipeline: Main generation orchestrator
- QueryPlanningPipeline: Multi-step agentic planning
- SchemaAnalyzer, FieldMetadataInferencer: LLM-powered schema enrichment
- ExtractionStrategy: Dialect-specific query extraction

Usage:
    from app.contextforge.generation import (
        QueryGenerationPipeline,
        QueryPlanningPipeline,
        get_strategy,
    )
    
    pipeline = QueryGenerationPipeline(
        llm_client=llm_client,
        schema_store=schema_store,
    )
    
    result = await pipeline.generate_query(
        tenant_id="acme",
        document_name="orders",
        user_question="Show pending orders",
    )
"""

from .pipeline import (
    QueryGenerationPipeline,
    calculate_confidence,
)
from .planning import (
    QueryPlanningPipeline,
)
from .inference import (
    SchemaAnalyzer,
    FieldMetadataInferencer,
    QAGenerator,
    InferenceValidator,
)
from .strategies import (
    ExtractionStrategy,
    SqlExtractionStrategy,
    OpenSearchExtractionStrategy,
    RestAPIExtractionStrategy,
    get_strategy,
)
from .prompt_templates import (
    get_schema_analysis_prompt,
    get_field_inference_prompt,
    get_qa_generation_prompt,
    get_query_generation_prompt,
    get_prompt_config,
    SCHEMA_ANALYSIS_PROMPTS,
    FIELD_INFERENCE_PROMPTS,
    QA_GENERATION_PROMPTS,
    QUERY_GENERATION_PROMPTS,
)

__all__ = [
    # Pipeline
    "QueryGenerationPipeline",
    "calculate_confidence",
    # Planning
    "QueryPlanningPipeline",
    # Inference
    "SchemaAnalyzer",
    "FieldMetadataInferencer",
    "QAGenerator",
    "InferenceValidator",
    # Strategies
    "ExtractionStrategy",
    "SqlExtractionStrategy",
    "OpenSearchExtractionStrategy",
    "RestAPIExtractionStrategy",
    "get_strategy",
    # Prompts
    "get_schema_analysis_prompt",
    "get_field_inference_prompt",
    "get_qa_generation_prompt",
    "get_query_generation_prompt",
    "get_prompt_config",
    "SCHEMA_ANALYSIS_PROMPTS",
    "FIELD_INFERENCE_PROMPTS",
    "QA_GENERATION_PROMPTS",
    "QUERY_GENERATION_PROMPTS",
]
