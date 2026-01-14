"""
Settings request/response schemas.
"""

from typing import Optional
from pydantic import BaseModel, Field


class SearchSettings(BaseModel):
    """Search configuration settings."""
    
    bm25_weight: float = Field(0.4, ge=0, le=1)
    vector_weight: float = Field(0.6, ge=0, le=1)
    default_limit: int = Field(10, ge=1, le=100)


class PipelineSettings(BaseModel):
    """Pipeline configuration settings."""
    
    similarity_skip_threshold: float = Field(0.95, ge=0, le=1)
    similarity_variant_threshold: float = Field(0.85, ge=0, le=1)
    similarity_merge_threshold: float = Field(0.70, ge=0, le=1)
    confidence_threshold: float = Field(0.7, ge=0, le=1)
    min_body_length: int = Field(30, ge=1)
    min_closure_notes_length: int = Field(30, ge=1)


class MaintenanceSettings(BaseModel):
    """Maintenance configuration settings."""
    
    version_retention_days: int = Field(90, ge=1, le=365)
    hit_retention_days: int = Field(365, ge=1, le=1825)


class SettingsResponse(BaseModel):
    """Response schema for all settings."""
    
    search: SearchSettings
    pipeline: PipelineSettings
    maintenance: MaintenanceSettings


class SettingsUpdateRequest(BaseModel):
    """Request schema for updating settings (partial update)."""
    
    search: Optional[SearchSettings] = None
    pipeline: Optional[PipelineSettings] = None
    maintenance: Optional[MaintenanceSettings] = None
