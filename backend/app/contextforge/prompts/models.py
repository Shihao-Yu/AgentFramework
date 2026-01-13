"""
Prompt Management Models for ContextForge.

Defines Pydantic models for prompt templates, versions, and configuration.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PromptCategory(str, Enum):
    """Categories of prompts in the system."""
    SCHEMA_ANALYSIS = "schema_analysis"
    FIELD_INFERENCE = "field_inference"
    QA_GENERATION = "qa_generation"
    QUERY_GENERATION = "query_generation"
    DISAMBIGUATION = "disambiguation"
    VALIDATION = "validation"
    PLANNING = "planning"


class PromptDialect(str, Enum):
    """Supported database/query dialects."""
    POSTGRES = "postgres"
    MYSQL = "mysql"
    CLICKHOUSE = "clickhouse"
    OPENSEARCH = "opensearch"
    REST_API = "rest_api"
    MONGODB = "mongodb"
    DEFAULT = "default"


class PromptTemplate(BaseModel):
    """
    A prompt template with metadata.
    
    Templates use Jinja2/Python format strings with named placeholders.
    """
    id: Optional[str] = Field(default=None, description="Unique identifier")
    name: str = Field(..., description="Template name (e.g., 'query_generation_postgres')")
    category: PromptCategory = Field(..., description="Prompt category")
    dialect: PromptDialect = Field(default=PromptDialect.DEFAULT)
    
    content: str = Field(..., description="Template content with {placeholders}")
    variables: List[str] = Field(default_factory=list, description="Expected placeholder names")
    
    description: Optional[str] = Field(default=None, description="What this prompt does")
    version: int = Field(default=1, description="Template version number")
    is_active: bool = Field(default=True, description="Whether this version is active")
    
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    
    model_config = ConfigDict(use_enum_values=True)
    
    def render(self, **kwargs: Any) -> str:
        """
        Render template with provided variables.
        
        Uses str.format() for simple substitution.
        Missing variables will raise KeyError.
        """
        return self.content.format(**kwargs)
    
    def render_safe(self, **kwargs: Any) -> str:
        """
        Render template, leaving missing placeholders intact.
        
        Useful for partial rendering or debugging.
        """
        result = self.content
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return result
    
    def get_missing_variables(self, provided: Dict[str, Any]) -> List[str]:
        """Return list of required variables not in provided dict."""
        return [v for v in self.variables if v not in provided]


class PromptVersion(BaseModel):
    """
    Version history entry for a prompt template.
    
    Tracks changes over time for audit and rollback.
    """
    id: Optional[str] = Field(default=None)
    template_id: str = Field(..., description="Parent template ID")
    template_name: str = Field(..., description="Template name at this version")
    
    version: int = Field(..., description="Version number")
    content: str = Field(..., description="Template content at this version")
    variables: List[str] = Field(default_factory=list)
    
    is_active: bool = Field(default=False, description="Whether this is the active version")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None)
    change_reason: Optional[str] = Field(default=None, description="Why this version was created")
    
    model_config = ConfigDict(use_enum_values=True)


class PromptConfig(BaseModel):
    """
    Configuration for prompt management behavior.
    """
    default_dialect: PromptDialect = Field(
        default=PromptDialect.DEFAULT,
        description="Default dialect when not specified"
    )
    fallback_enabled: bool = Field(
        default=True,
        description="Fall back to file-based prompts if DB lookup fails"
    )
    cache_enabled: bool = Field(
        default=True,
        description="Enable in-memory caching of prompts"
    )
    cache_ttl_seconds: int = Field(
        default=300,
        description="Cache time-to-live in seconds"
    )
    langfuse_sync_enabled: bool = Field(
        default=False,
        description="Sync prompts with Langfuse"
    )
    
    model_config = ConfigDict(use_enum_values=True)


class PromptLookupKey(BaseModel):
    """
    Key for looking up a prompt template.
    """
    name: str = Field(..., description="Template name")
    category: Optional[PromptCategory] = Field(default=None)
    dialect: PromptDialect = Field(default=PromptDialect.DEFAULT)
    version: Optional[int] = Field(default=None, description="Specific version, or None for latest")
    
    def to_storage_key(self) -> str:
        """Generate a unique key for storage lookup."""
        parts = [self.name]
        if self.category:
            parts.append(self.category)
        parts.append(self.dialect)
        return "_".join(parts)
    
    model_config = ConfigDict(use_enum_values=True)
