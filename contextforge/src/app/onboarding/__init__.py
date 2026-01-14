"""
Onboarding pipelines for extracting structured knowledge from raw text.

This module provides type-specific pipelines that use LLM structured output
to extract knowledge nodes (FAQ, Playbook, Concept, etc.) from unstructured text.
"""

from app.onboarding.base import OnboardingPipeline
from app.onboarding.models import (
    FAQExtraction,
    PlaybookExtraction,
    ConceptExtraction,
    FeaturePermissionExtraction,
    EntityExtraction,
)
from app.onboarding.faq_pipeline import FAQPipeline
from app.onboarding.playbook_pipeline import PlaybookPipeline
from app.onboarding.concept_pipeline import ConceptPipeline
from app.onboarding.feature_permission_pipeline import FeaturePermissionPipeline
from app.onboarding.entity_pipeline import EntityPipeline

__all__ = [
    "OnboardingPipeline",
    "FAQExtraction",
    "PlaybookExtraction",
    "ConceptExtraction",
    "FeaturePermissionExtraction",
    "EntityExtraction",
    "FAQPipeline",
    "PlaybookPipeline",
    "ConceptPipeline",
    "FeaturePermissionPipeline",
    "EntityPipeline",
]
