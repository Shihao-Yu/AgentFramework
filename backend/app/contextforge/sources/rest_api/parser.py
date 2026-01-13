"""
OpenAPI/Swagger Specification Parser.

Parses OpenAPI 3.0+ and Swagger 2.0 specifications into ContextForge
schema models (EndpointSpec, ParameterSpec, ConceptSpec).
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ...schema.api_schema import (
        EndpointSpec,
        ParameterSpec,
        APISchemaInfo,
        SecuritySchemeSpec,
    )
    from ...schema.yaml_schema import ConceptSpec

logger = logging.getLogger(__name__)


class OpenAPIParser:
    """
    Parse OpenAPI/Swagger specifications into ContextForge schema format.
    
    Handles OpenAPI 3.0.x, 3.1.x and Swagger 2.0.
    """
    
    def __init__(self, spec: Dict[str, Any]):
        self.spec = spec
        self.version = self._detect_version()
        self._ref_cache: Dict[str, Any] = {}
    
    def _detect_version(self) -> str:
        if "openapi" in self.spec:
            return self.spec["openapi"]
        elif "swagger" in self.spec:
            return f"swagger-{self.spec['swagger']}"
        return "unknown"
    
    def parse(self) -> Tuple[List["EndpointSpec"], List["ConceptSpec"]]:
        """Parse the specification into endpoints and concepts."""
        logger.info(f"Parsing OpenAPI spec version: {self.version}")
        
        endpoints = self._parse_paths()
        concepts = self._infer_concepts(endpoints)
        
        logger.info(f"Parsed {len(endpoints)} endpoints, inferred {len(concepts)} concepts")
        
        return endpoints, concepts
    
    def get_api_info(self) -> "APISchemaInfo":
        """Extract API metadata from info section."""
        from ...schema.api_schema import APISchemaInfo
        
        info = self.spec.get("info", {})
        servers = self.spec.get("servers", [])
        
        base_url = None
        server_urls = []
        if servers:
            base_url = servers[0].get("url")
            server_urls = [s.get("url") for s in servers if s.get("url")]
        elif "host" in self.spec:
            scheme = self.spec.get("schemes", ["https"])[0]
            base_path = self.spec.get("basePath", "")
            base_url = f"{scheme}://{self.spec['host']}{base_path}"
            server_urls = [base_url]
        
        contact = info.get("contact", {})
        
        return APISchemaInfo(
            title=info.get("title", "Untitled API"),
            version=info.get("version", "1.0.0"),
            description=info.get("description"),
            base_url=base_url,
            servers=server_urls,
            contact_name=contact.get("name"),
            contact_email=contact.get("email"),
            openapi_version=self.version,
        )
    
    def get_security_schemes(self) -> List["SecuritySchemeSpec"]:
        """Extract security scheme definitions."""
        from ...schema.api_schema import SecuritySchemeSpec
        
        schemes = []
        
        components = self.spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        
        if not security_schemes:
            security_schemes = self.spec.get("securityDefinitions", {})
        
        for name, scheme in security_schemes.items():
            schemes.append(SecuritySchemeSpec(
                name=name,
                type=scheme.get("type", "unknown"),
                api_key_name=scheme.get("name"),
                api_key_location=scheme.get("in"),
                scheme=scheme.get("scheme"),
                bearer_format=scheme.get("bearerFormat"),
                oauth_flows=scheme.get("flows"),
                description=scheme.get("description"),
            ))
        
        return schemes
    
    def _parse_paths(self) -> List["EndpointSpec"]:
        """Parse paths section into EndpointSpec list."""
        from ...schema.api_schema import EndpointSpec, HTTPMethod
        
        endpoints = []
        paths = self.spec.get("paths", {})
        
        for path, path_item in paths.items():
            path_level_params = path_item.get("parameters", [])
            
            for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                if method in path_item:
                    operation = path_item[method]
                    endpoint = self._parse_operation(
                        path, 
                        method.upper(), 
                        operation,
                        path_level_params
                    )
                    endpoints.append(endpoint)
        
        return endpoints
    
    def _parse_operation(
        self,
        path: str,
        method: str,
        operation: Dict[str, Any],
        path_level_params: List[Dict[str, Any]],
    ) -> "EndpointSpec":
        """Parse single operation into EndpointSpec."""
        from ...schema.api_schema import EndpointSpec, HTTPMethod
        
        parameters = []
        
        for param in path_level_params:
            parsed = self._parse_parameter(param)
            if parsed:
                parameters.append(parsed)
        
        for param in operation.get("parameters", []):
            parsed = self._parse_parameter(param)
            if parsed:
                existing_idx = next(
                    (i for i, p in enumerate(parameters) 
                     if p.name == parsed.name and p.location == parsed.location),
                    None
                )
                if existing_idx is not None:
                    parameters[existing_idx] = parsed
                else:
                    parameters.append(parsed)
        
        if "requestBody" in operation:
            body_params = self._parse_request_body(operation["requestBody"])
            parameters.extend(body_params)
        
        maps_to = self._infer_concept_from_path(path)
        tags = operation.get("tags", [])
        if not maps_to and tags:
            maps_to = self._normalize_concept_name(tags[0])
        
        auth_required = bool(operation.get("security", self.spec.get("security")))
        
        return EndpointSpec(
            path=path,
            method=HTTPMethod(method),
            operation_id=operation.get("operationId"),
            summary=operation.get("summary"),
            description=operation.get("description"),
            maps_to=maps_to,
            tags=tags,
            parameters=parameters,
            deprecated=operation.get("deprecated", False),
            auth_required=auth_required,
        )
    
    def _parse_parameter(self, param: Dict[str, Any]) -> Optional["ParameterSpec"]:
        """Parse OpenAPI parameter into ParameterSpec."""
        from ...schema.api_schema import ParameterSpec, ParameterLocation
        
        if "$ref" in param:
            param = self._resolve_ref(param["$ref"])
            if not param:
                return None
        
        schema = param.get("schema", param)
        param_type = schema.get("type", "string")
        items_type = None
        if param_type == "array":
            items = schema.get("items", {})
            items_type = items.get("type", "string")
        
        allowed_values = schema.get("enum")
        
        value_synonyms = {}
        description = param.get("description", "")
        if allowed_values and description:
            value_synonyms = self._infer_synonyms_from_description(
                allowed_values, description
            )
        
        value_examples = []
        if "example" in param:
            value_examples.append(str(param["example"]))
        if "example" in schema:
            value_examples.append(str(schema["example"]))
        
        maps_to = self._infer_concept_from_param_name(param["name"])
        
        return ParameterSpec(
            name=param["name"],
            location=ParameterLocation(param["in"]),
            param_type=param_type,
            description=description or None,
            maps_to=maps_to,
            required=param.get("required", False),
            allowed_values=allowed_values,
            value_synonyms=value_synonyms,
            value_examples=value_examples,
            default_value=schema.get("default"),
            format=schema.get("format"),
            pattern=schema.get("pattern"),
            items_type=items_type,
            deprecated=param.get("deprecated", False),
        )
    
    def _parse_request_body(self, request_body: Dict[str, Any]) -> List["ParameterSpec"]:
        """Parse OpenAPI 3.x requestBody into body parameters."""
        from ...schema.api_schema import ParameterSpec, ParameterLocation
        
        parameters = []
        
        if "$ref" in request_body:
            request_body = self._resolve_ref(request_body["$ref"])
            if not request_body:
                return parameters
        
        content = request_body.get("content", {})
        json_content = (
            content.get("application/json") or
            content.get("application/x-www-form-urlencoded") or
            next(iter(content.values()), {})
        )
        
        schema = json_content.get("schema", {})
        
        if "$ref" in schema:
            schema = self._resolve_ref(schema["$ref"])
            if not schema:
                return parameters
        
        required_props = set(schema.get("required", []))
        
        for prop_name, prop_schema in schema.get("properties", {}).items():
            if "$ref" in prop_schema:
                prop_schema = self._resolve_ref(prop_schema["$ref"])
                if not prop_schema:
                    continue
            
            param_type = prop_schema.get("type", "string")
            
            parameters.append(ParameterSpec(
                name=prop_name,
                location=ParameterLocation.BODY,
                param_type=param_type,
                description=prop_schema.get("description"),
                required=prop_name in required_props,
                allowed_values=prop_schema.get("enum"),
                default_value=prop_schema.get("default"),
                format=prop_schema.get("format"),
            ))
        
        return parameters
    
    def _infer_concepts(self, endpoints: List["EndpointSpec"]) -> List["ConceptSpec"]:
        """Infer business concepts from endpoints."""
        from ...schema.yaml_schema import ConceptSpec
        
        concept_map: Dict[str, ConceptSpec] = {}
        
        for endpoint in endpoints:
            if endpoint.maps_to:
                if endpoint.maps_to not in concept_map:
                    concept_map[endpoint.maps_to] = ConceptSpec(
                        name=endpoint.maps_to,
                        description=self._infer_concept_description(endpoint.maps_to, endpoints),
                        auto_suggested=True,
                        confidence=0.8,
                    )
            
            for param in endpoint.parameters:
                if param.maps_to and param.maps_to not in concept_map:
                    concept_map[param.maps_to] = ConceptSpec(
                        name=param.maps_to,
                        auto_suggested=True,
                        confidence=0.6,
                    )
        
        components = self.spec.get("components", {})
        schemas = components.get("schemas", {})
        
        if not schemas:
            schemas = self.spec.get("definitions", {})
        
        for schema_name, schema_def in schemas.items():
            concept_name = self._normalize_concept_name(schema_name)
            if concept_name not in concept_map:
                concept_map[concept_name] = ConceptSpec(
                    name=concept_name,
                    description=schema_def.get("description"),
                    auto_suggested=True,
                    confidence=0.7,
                )
        
        return list(concept_map.values())
    
    def _infer_concept_from_path(self, path: str) -> Optional[str]:
        """Infer primary concept from URL path."""
        clean = re.sub(r'/api/v\d+', '', path)
        clean = re.sub(r'/v\d+', '', clean)
        clean = re.sub(r'/\{[^}]+\}', '', clean)
        
        segments = [s for s in clean.split('/') if s and s != 'api']
        
        if not segments:
            return None
        
        concept = segments[-1]
        return self._normalize_concept_name(concept)
    
    def _infer_concept_from_param_name(self, param_name: str) -> Optional[str]:
        """Infer concept from parameter name patterns."""
        patterns = [
            (r'^(\w+)_id$', r'\1'),
            (r'^(\w+)Id$', r'\1'),
            (r'^(\w+)_ids$', r'\1'),
            (r'^(\w+)_code$', r'\1'),
            (r'^(\w+)_type$', r'\1'),
        ]
        
        for pattern, replacement in patterns:
            match = re.match(pattern, param_name, re.IGNORECASE)
            if match:
                return self._normalize_concept_name(match.group(1))
        
        return None
    
    def _normalize_concept_name(self, name: str) -> str:
        """Normalize concept name to lowercase, no special chars."""
        name = re.sub(r'^(get|list|create|update|delete|fetch)', '', name, flags=re.IGNORECASE)
        name = re.sub(r'(Request|Response|Dto|Model|Entity)$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'[-_\s]+', '', name.lower())
        
        if name.endswith('ies'):
            name = name[:-3] + 'y'
        elif name.endswith('es') and not name.endswith('ses'):
            name = name[:-2]
        elif name.endswith('s') and not name.endswith('ss'):
            name = name[:-1]
        
        return name
    
    def _infer_concept_description(
        self,
        concept_name: str,
        endpoints: List["EndpointSpec"],
    ) -> Optional[str]:
        """Infer concept description from endpoint descriptions."""
        for endpoint in endpoints:
            if endpoint.maps_to == concept_name:
                if endpoint.description:
                    return endpoint.description
                if endpoint.summary:
                    return endpoint.summary
        return None
    
    def _infer_synonyms_from_description(
        self,
        enum_values: List[str],
        description: str,
    ) -> Dict[str, List[str]]:
        """Extract value synonyms from parameter description."""
        synonyms: Dict[str, List[str]] = {}
        
        pattern1 = r'["\']?(\w+)["\']?\s*\(([^)]+)\)'
        for match in re.finditer(pattern1, description):
            value = match.group(1)
            meanings = [m.strip().lower() for m in match.group(2).split(',')]
            if value in enum_values:
                synonyms[value] = meanings
        
        pattern2 = r'["\']?(\w+)["\']?\s*[=:]\s*([^,;\|\n]+)'
        for match in re.finditer(pattern2, description):
            value = match.group(1)
            meaning = match.group(2).strip().lower()
            if value in enum_values and value not in synonyms:
                synonyms[value] = [meaning]
        
        return synonyms
    
    def _resolve_ref(self, ref: str) -> Optional[Dict[str, Any]]:
        """Resolve $ref to actual schema/parameter definition."""
        if ref in self._ref_cache:
            return self._ref_cache[ref]
        
        result = None
        
        if ref.startswith("#/"):
            parts = ref[2:].split("/")
            result = self.spec
            for part in parts:
                if isinstance(result, dict) and part in result:
                    result = result[part]
                else:
                    logger.warning(f"Could not resolve $ref: {ref}")
                    result = None
                    break
        
        self._ref_cache[ref] = result
        return result
