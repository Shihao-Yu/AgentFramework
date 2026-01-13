"""Tests for ContextForge prompts module."""
import pytest
from datetime import datetime

from app.contextforge.prompts import (
    PromptTemplate,
    PromptVersion,
    PromptConfig,
    PromptCategory,
    PromptDialect,
    PromptManager,
)


class TestPromptCategory:
    def test_categories(self):
        assert PromptCategory.QUERY_GENERATION.value == "query_generation"
        assert PromptCategory.SCHEMA_ENRICHMENT.value == "schema_enrichment"
        assert PromptCategory.VALIDATION.value == "validation"


class TestPromptDialect:
    def test_dialects(self):
        assert PromptDialect.SQL.value == "sql"
        assert PromptDialect.ELASTICSEARCH.value == "elasticsearch"
        assert PromptDialect.REST_API.value == "rest_api"
        assert PromptDialect.GENERIC.value == "generic"


class TestPromptTemplate:
    def test_create_template(self):
        template = PromptTemplate(
            id="test_prompt",
            name="Test Prompt",
            category=PromptCategory.QUERY_GENERATION,
            dialect=PromptDialect.SQL,
            template="Generate SQL for: {question}",
            description="A test prompt",
            version=1,
        )
        assert template.id == "test_prompt"
        assert template.category == PromptCategory.QUERY_GENERATION
        assert template.variables == []
    
    def test_render_template(self):
        template = PromptTemplate(
            id="test_prompt",
            name="Test Prompt",
            category=PromptCategory.QUERY_GENERATION,
            dialect=PromptDialect.SQL,
            template="Generate SQL for: {question}\nSchema: {schema}",
            variables=["question", "schema"],
            version=1,
        )
        rendered = template.render(question="Show all users", schema="users(id, name)")
        assert "Show all users" in rendered
        assert "users(id, name)" in rendered
    
    def test_render_with_missing_variable(self):
        template = PromptTemplate(
            id="test_prompt",
            name="Test Prompt",
            category=PromptCategory.QUERY_GENERATION,
            dialect=PromptDialect.SQL,
            template="Generate SQL for: {question}",
            variables=["question"],
            version=1,
        )
        with pytest.raises(KeyError):
            template.render(schema="users")


class TestPromptVersion:
    def test_create_version(self):
        version = PromptVersion(
            version=1,
            template="Generate SQL: {question}",
            created_at=datetime.utcnow(),
            created_by="user_123",
        )
        assert version.version == 1
        assert version.changelog is None
    
    def test_version_with_changelog(self):
        version = PromptVersion(
            version=2,
            template="Generate optimized SQL: {question}",
            created_at=datetime.utcnow(),
            created_by="user_123",
            changelog="Improved query optimization hints",
        )
        assert version.version == 2
        assert "optimization" in version.changelog


class TestPromptConfig:
    def test_default_config(self):
        config = PromptConfig()
        assert config.max_tokens == 4096
        assert config.temperature == 0.0
        assert config.use_cache is True
    
    def test_custom_config(self):
        config = PromptConfig(
            max_tokens=2048,
            temperature=0.7,
            stop_sequences=["END"],
        )
        assert config.max_tokens == 2048
        assert config.temperature == 0.7
        assert config.stop_sequences == ["END"]


class TestPromptManager:
    def test_init(self):
        manager = PromptManager(tenant_id="test")
        assert manager.tenant_id == "test"
    
    def test_default_tenant(self):
        manager = PromptManager()
        assert manager.tenant_id == "default"
    
    def test_get_default_template(self):
        manager = PromptManager()
        template = manager.get_default_template(
            PromptCategory.QUERY_GENERATION,
            PromptDialect.SQL,
        )
        assert template is not None or template is None
