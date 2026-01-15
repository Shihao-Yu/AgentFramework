"""
Knowledge Verse node schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field, field_validator

from app.models.enums import NodeType, KnowledgeStatus, Visibility


# =============================================================================
# Content schemas for each node type
# =============================================================================

class FAQContent(BaseModel):
    """FAQ content - question and answer pair."""
    answer: str = Field(..., min_length=1)
    variants: List[str] = Field(default=[])


class PlaybookStep(BaseModel):
    order: int
    action: str
    owner: Optional[str] = None
    details: Optional[str] = None


class PlaybookContent(BaseModel):
    description: str = Field(..., min_length=1)
    steps: List[PlaybookStep] = Field(default=[], min_length=1)
    prerequisites: List[str] = Field(default=[])
    estimated_time: Optional[str] = None
    related_forms: List[str] = Field(default=[])


class PermissionRule(BaseModel):
    role: str
    action: str
    constraint: Optional[Dict[str, Any]] = None


class PermissionRuleContent(BaseModel):
    feature: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    rules: List[PermissionRule] = Field(default=[], min_length=1)
    escalation_path: List[str] = Field(default=[])


class EntityAttribute(BaseModel):
    name: str
    type: str
    description: Optional[str] = None


class EntityOperation(BaseModel):
    action: str
    description: Optional[str] = None


class EntityContent(BaseModel):
    entity_name: str = Field(..., min_length=1)
    entity_path: str = Field(..., min_length=1)
    parent_entity: Optional[str] = None
    child_entities: List[str] = Field(default=[])
    description: str = Field(..., min_length=1)
    business_purpose: Optional[str] = None
    key_attributes: List[EntityAttribute] = Field(default=[])
    common_operations: List[EntityOperation] = Field(default=[])
    common_queries: List[str] = Field(default=[])


class ForeignKey(BaseModel):
    column: str
    references: str


class SchemaIndexContent(BaseModel):
    source_type: str = Field(..., pattern="^(postgres|elasticsearch|api)$")
    database: Optional[str] = None
    schema_name: Optional[str] = Field(None, alias="schema")
    table_name: Optional[str] = None
    index_name: Optional[str] = None
    endpoint: Optional[str] = None
    description: str = Field(..., min_length=1)
    primary_key: List[str] = Field(default=[])
    foreign_keys: List[ForeignKey] = Field(default=[])
    query_patterns: List[str] = Field(default=[])
    row_count_estimate: Optional[int] = None
    update_frequency: Optional[str] = None


class SchemaFieldContent(BaseModel):
    description: str = Field(..., min_length=1)
    business_meaning: Optional[str] = None
    allowed_values: List[str] = Field(default=[])
    default_value: Optional[Any] = None
    nullable: bool = True
    indexed: bool = False
    search_patterns: List[str] = Field(default=[])
    business_rules: List[str] = Field(default=[])


class ExampleContent(BaseModel):
    question: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    query_type: str = Field(..., pattern="^(sql|elasticsearch|api)$")
    explanation: Optional[str] = None
    verified: bool = False


class ConceptContent(BaseModel):
    description: str = Field(..., min_length=1)
    aliases: List[str] = Field(default=[])
    scope: Optional[str] = None
    key_questions: List[str] = Field(default=[])


NodeContentType = Union[
    FAQContent,
    PlaybookContent,
    PermissionRuleContent,
    EntityContent,
    SchemaIndexContent,
    SchemaFieldContent,
    ExampleContent,
    ConceptContent,
]


# =============================================================================
# Node request/response schemas
# =============================================================================

class NodeListParams(BaseModel):
    tenant_ids: Optional[List[str]] = None
    node_types: Optional[List[NodeType]] = None
    status: Optional[KnowledgeStatus] = None
    visibility: Optional[Visibility] = None
    tags: Optional[List[str]] = None
    dataset_name: Optional[str] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class NodeCreate(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=100)
    node_type: NodeType
    title: str = Field(..., min_length=1, max_length=500)
    summary: Optional[str] = None
    content: Dict[str, Any]
    tags: List[str] = Field(default=[])
    dataset_name: Optional[str] = None
    field_path: Optional[str] = None
    data_type: Optional[str] = None
    visibility: Visibility = Visibility.INTERNAL
    status: KnowledgeStatus = KnowledgeStatus.DRAFT
    source: str = "manual"
    source_reference: Optional[str] = None
    metadata_: Dict[str, Any] = Field(default={})

    @field_validator("content")
    @classmethod
    def validate_content_for_type(cls, v: Dict[str, Any], info) -> Dict[str, Any]:
        node_type = info.data.get("node_type")
        if not node_type:
            return v
        
        content_validators = {
            NodeType.FAQ: FAQContent,
            NodeType.PLAYBOOK: PlaybookContent,
            NodeType.PERMISSION_RULE: PermissionRuleContent,
            NodeType.ENTITY: EntityContent,
            NodeType.SCHEMA_INDEX: SchemaIndexContent,
            NodeType.SCHEMA_FIELD: SchemaFieldContent,
            NodeType.EXAMPLE: ExampleContent,
            NodeType.CONCEPT: ConceptContent,
        }
        
        validator = content_validators.get(node_type)
        if validator:
            validator.model_validate(v)
        
        return v


class NodeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    summary: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    dataset_name: Optional[str] = None
    field_path: Optional[str] = None
    data_type: Optional[str] = None
    visibility: Optional[Visibility] = None
    status: Optional[KnowledgeStatus] = None
    metadata_: Optional[Dict[str, Any]] = None


class NodeResponse(BaseModel):
    id: int
    tenant_id: str
    node_type: NodeType
    title: str
    summary: Optional[str] = None
    content: Dict[str, Any]
    tags: List[str]
    dataset_name: Optional[str] = None
    field_path: Optional[str] = None
    data_type: Optional[str] = None
    visibility: Visibility
    status: KnowledgeStatus
    source: str
    source_reference: Optional[str] = None
    version: int
    metadata_: Dict[str, Any] = Field(default={})
    created_by: Optional[str] = None
    created_at: datetime
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    
    edges_count: Optional[int] = None
    
    class Config:
        from_attributes = True


class NodeDetailResponse(NodeResponse):
    incoming_edges: Optional[List["EdgeResponse"]] = None
    outgoing_edges: Optional[List["EdgeResponse"]] = None


class NodeSearchResult(BaseModel):
    node: NodeResponse
    bm25_rank: Optional[int] = None
    vector_rank: Optional[int] = None
    bm25_score: Optional[float] = None
    vector_score: Optional[float] = None
    rrf_score: float
    match_source: Optional[str] = None


class NodeSearchResponse(BaseModel):
    results: List[NodeSearchResult]
    total: int
    page: int
    limit: int


class NodeVersionResponse(BaseModel):
    id: int
    node_id: int
    version_number: int
    title: str
    content: Dict[str, Any]
    tags: Optional[List[str]] = None
    change_type: Optional[str] = None
    changed_by: Optional[str] = None
    changed_at: datetime
    
    class Config:
        from_attributes = True


from app.schemas.edges import EdgeResponse
NodeDetailResponse.model_rebuild()
