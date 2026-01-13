"""
REST API Schema Models for OpenAPI/Swagger Specification Support.

Defines Pydantic models for REST API endpoints that parallel the OpenSearch
schema models (IndexSpec, FieldSpec) to enable unified graph-based retrieval.

Key Design Principles:
- ParameterSpec parallels FieldSpec (both have value_synonyms, maps_to, etc.)
- EndpointSpec parallels IndexSpec (both contain fields/parameters)
- Concepts are SHARED across OpenSearch and REST API data sources
- Parameters can convert to FieldSpec for unified graph indexing
"""

from __future__ import annotations

import re
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from .yaml_schema import FieldSpec

logger = logging.getLogger(__name__)


class HTTPMethod(str, Enum):
    """Supported HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ParameterLocation(str, Enum):
    """Where the parameter is located in the HTTP request."""
    QUERY = "query"
    PATH = "path"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"


class ParameterSpec(BaseModel):
    """
    REST API parameter specification.
    
    Designed to parallel FieldSpec for unified graph indexing:
    - name -> path (qualified as "{location}.{name}")
    - param_type -> es_type equivalent
    - value_synonyms -> same semantic mapping
    - maps_to -> same concept linking
    
    Example YAML:
        parameters:
          - name: status
            location: query
            param_type: string
            description: Order status filter
            allowed_values: ['P', 'R', 'C', 'X']
            value_synonyms:
              P: [pending, waiting, open]
              R: [released, approved]
            maps_to: purchaseorder
    """
    # Core identity
    name: str = Field(..., description="Parameter name")
    location: ParameterLocation = Field(..., description="Location: query, path, header, body")
    param_type: str = Field("string", description="JSON Schema type")
    
    # Semantic info (shared with FieldSpec)
    description: Optional[str] = Field(None, description="Human-readable description")
    maps_to: Optional[str] = Field(None, description="Business concept this parameter maps to")
    business_meaning: str = Field(default="", description="Business context and usage")
    
    # Constraints
    required: bool = Field(False, description="Is this parameter required?")
    default_value: Optional[Any] = Field(None, description="Default value")
    
    # Value constraints (SAME as FieldSpec for unified handling)
    allowed_values: Optional[List[str]] = Field(
        None, 
        description="Valid enum values"
    )
    value_synonyms: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Maps canonical values to synonyms"
    )
    value_examples: List[str] = Field(
        default_factory=list,
        description="Example values"
    )
    
    # API-specific metadata
    format: Optional[str] = Field(None, description="Format hint: date-time, email, uuid")
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")
    min_length: Optional[int] = Field(None)
    max_length: Optional[int] = Field(None)
    minimum: Optional[float] = Field(None)
    maximum: Optional[float] = Field(None)
    
    # Array-specific
    items_type: Optional[str] = Field(None, description="Type of array items")
    
    # Metadata
    deprecated: bool = Field(False)
    human_edited: bool = Field(False)
    last_updated: Optional[datetime] = Field(None)
    
    model_config = ConfigDict(use_enum_values=True)
    
    @field_validator('location', mode='before')
    @classmethod
    def validate_location(cls, v):
        """Convert string to ParameterLocation enum."""
        if isinstance(v, str):
            return ParameterLocation(v.lower())
        return v
    
    @field_validator('maps_to')
    @classmethod
    def normalize_maps_to(cls, v: Optional[str]) -> Optional[str]:
        """Normalize concept name to lowercase."""
        return v.lower().strip() if v else None
    
    def get_qualified_name(self) -> str:
        """Get qualified parameter name: {location}.{name}."""
        return f"{self.location}.{self.name}"
    
    def to_field_spec(self, parent_endpoint: str = "") -> "FieldSpec":
        """
        Convert to FieldSpec for unified graph indexing.
        
        This enables parameters to be indexed alongside fields
        in the SchemaGraph, allowing unified concept-based retrieval.
        """
        from .yaml_schema import FieldSpec as YAMLFieldSpec
        
        return YAMLFieldSpec(
            path=self.get_qualified_name(),
            es_type=self._map_type_to_es(),
            description=self.description,
            maps_to=self.maps_to,
            business_meaning=self.business_meaning,
            allowed_values=self.allowed_values,
            value_synonyms=self.value_synonyms,
            value_examples=self.value_examples,
            is_required=self.required,
            human_edited=self.human_edited,
            last_updated=self.last_updated,
        )
    
    def _map_type_to_es(self) -> str:
        """Map JSON Schema types to field type equivalents."""
        type_mapping = {
            "string": "text",
            "integer": "long",
            "number": "float",
            "boolean": "boolean",
            "array": "nested",
            "object": "object",
        }
        return type_mapping.get(self.param_type, "text")
    
    def get_canonical_value(self, synonym: str) -> Optional[str]:
        """
        Find the canonical value for a synonym.
        
        Args:
            synonym: A value synonym to look up (case-insensitive)
        
        Returns:
            The canonical value if found, None otherwise
        """
        synonym_lower = synonym.lower()
        for canonical, synonyms in self.value_synonyms.items():
            if synonym_lower == canonical.lower():
                return canonical
            if synonym_lower in [s.lower() for s in synonyms]:
                return canonical
        return None


class ResponseFieldSpec(BaseModel):
    """
    Field in API response body.
    
    Used to understand what data an endpoint returns, enabling
    better context for query generation.
    """
    path: str = Field(..., description="JSON path in response")
    field_type: str = Field("string", description="JSON Schema type")
    description: Optional[str] = Field(None)
    maps_to: Optional[str] = Field(None, description="Business concept")
    nullable: bool = Field(False)
    
    @field_validator('maps_to')
    @classmethod
    def normalize_maps_to(cls, v: Optional[str]) -> Optional[str]:
        return v.lower().strip() if v else None


class RequestBodySpec(BaseModel):
    """
    Request body specification for POST/PUT/PATCH endpoints.
    
    Extracted from OpenAPI requestBody schema.
    """
    content_type: str = Field("application/json", description="Content-Type header")
    required: bool = Field(False)
    description: Optional[str] = Field(None)


class EndpointSpec(BaseModel):
    """
    REST API endpoint specification.
    
    Parallels IndexSpec for OpenSearch - both are containers for
    searchable fields/parameters mapped to business concepts.
    
    Example YAML:
        endpoints:
          - path: /api/orders
            method: GET
            operation_id: listOrders
            description: List all orders with optional filters
            maps_to: purchaseorder
            parameters:
              - name: status
                location: query
                ...
    """
    # Endpoint identity
    path: str = Field(..., description="URL path template")
    method: HTTPMethod = Field(..., description="HTTP method")
    operation_id: Optional[str] = Field(None, description="Unique operation identifier")
    
    # Semantic info
    summary: Optional[str] = Field(None, description="Short summary")
    description: Optional[str] = Field(None, description="Detailed description")
    maps_to: Optional[str] = Field(None, description="Primary business concept")
    tags: List[str] = Field(default_factory=list, description="OpenAPI tags")
    
    # Parameters (like fields in IndexSpec)
    parameters: List[ParameterSpec] = Field(
        default_factory=list,
        description="All parameters (query, path, header, body)"
    )
    
    # Response info
    response_fields: List[ResponseFieldSpec] = Field(
        default_factory=list,
        description="Fields in the response body"
    )
    success_status_codes: List[int] = Field(
        default_factory=lambda: [200],
        description="HTTP status codes indicating success"
    )
    
    # API metadata
    auth_required: bool = Field(True, description="Requires authentication")
    auth_schemes: List[str] = Field(default_factory=list, description="Supported auth schemes")
    rate_limit: Optional[str] = Field(None, description="Rate limit info")
    deprecated: bool = Field(False)
    
    # Server info
    base_url: Optional[str] = Field(None, description="Base URL if different from default")
    
    # Metadata
    human_edited: bool = Field(False)
    last_updated: Optional[datetime] = Field(None)
    
    model_config = ConfigDict(use_enum_values=True)
    
    @field_validator('method', mode='before')
    @classmethod
    def validate_method(cls, v):
        """Convert string to HTTPMethod enum."""
        if isinstance(v, str):
            return HTTPMethod(v.upper())
        return v
    
    @field_validator('maps_to')
    @classmethod
    def normalize_maps_to(cls, v: Optional[str]) -> Optional[str]:
        return v.lower().strip() if v else None
    
    def get_qualified_name(self) -> str:
        """Unique identifier: GET:/api/orders/{order_id}."""
        return f"{self.method}:{self.path}"
    
    def get_parameters_by_location(self, location: ParameterLocation) -> List[ParameterSpec]:
        """Get all parameters in a specific location."""
        return [p for p in self.parameters if p.location == location]
    
    def get_query_params(self) -> List[ParameterSpec]:
        """Get query string parameters."""
        return self.get_parameters_by_location(ParameterLocation.QUERY)
    
    def get_path_params(self) -> List[ParameterSpec]:
        """Get path parameters."""
        return self.get_parameters_by_location(ParameterLocation.PATH)
    
    def get_body_params(self) -> List[ParameterSpec]:
        """Get request body parameters."""
        return self.get_parameters_by_location(ParameterLocation.BODY)
    
    def get_header_params(self) -> List[ParameterSpec]:
        """Get header parameters."""
        return self.get_parameters_by_location(ParameterLocation.HEADER)
    
    def get_path_param_names(self) -> List[str]:
        """Extract path parameter names from path template."""
        return re.findall(r'\{(\w+)\}', self.path)
    
    def get_required_params(self) -> List[ParameterSpec]:
        """Get all required parameters."""
        return [p for p in self.parameters if p.required]
    
    def get_parameter(self, name: str, location: Optional[ParameterLocation] = None) -> Optional[ParameterSpec]:
        """Get a parameter by name, optionally filtered by location."""
        for param in self.parameters:
            if param.name == name:
                if location is None or param.location == location:
                    return param
        return None
    
    def get_all_field_specs(self) -> List["FieldSpec"]:
        """Convert all parameters to FieldSpecs for graph indexing."""
        return [p.to_field_spec(self.path) for p in self.parameters]
    
    def get_concepts_used(self) -> List[str]:
        """Get all concepts referenced by this endpoint and its parameters."""
        concepts = set()
        if self.maps_to:
            concepts.add(self.maps_to)
        for param in self.parameters:
            if param.maps_to:
                concepts.add(param.maps_to)
        for field in self.response_fields:
            if field.maps_to:
                concepts.add(field.maps_to)
        return list(concepts)


class APISchemaInfo(BaseModel):
    """
    Metadata about the API specification.
    
    Extracted from OpenAPI info section.
    """
    title: str = Field(..., description="API title")
    version: str = Field(..., description="API version")
    description: Optional[str] = Field(None)
    
    # Server info
    base_url: Optional[str] = Field(None, description="Default base URL")
    servers: List[str] = Field(default_factory=list, description="Available server URLs")
    
    # Contact
    contact_name: Optional[str] = Field(None)
    contact_email: Optional[str] = Field(None)
    
    # Source
    openapi_version: Optional[str] = Field(None, description="OpenAPI spec version")
    source_file: Optional[str] = Field(None, description="Original spec file path")


class SecuritySchemeSpec(BaseModel):
    """
    API security scheme specification.
    
    Extracted from OpenAPI securitySchemes.
    """
    name: str = Field(..., description="Scheme name")
    type: str = Field(..., description="Type: apiKey, http, oauth2, openIdConnect")
    
    # For apiKey
    api_key_name: Optional[str] = Field(None, description="Header/query param name")
    api_key_location: Optional[str] = Field(None, description="Where API key is sent")
    
    # For http
    scheme: Optional[str] = Field(None, description="HTTP auth scheme: bearer, basic")
    bearer_format: Optional[str] = Field(None, description="Bearer token format hint")
    
    # For oauth2
    oauth_flows: Optional[Dict[str, Any]] = Field(None, description="OAuth2 flow configurations")
    
    description: Optional[str] = Field(None)
