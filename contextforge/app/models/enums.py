from enum import Enum


class NodeType(str, Enum):
    FAQ = "faq"
    PLAYBOOK = "playbook"
    PERMISSION_RULE = "permission_rule"
    SCHEMA_INDEX = "schema_index"
    SCHEMA_FIELD = "schema_field"
    EXAMPLE = "example"
    ENTITY = "entity"
    CONCEPT = "concept"
    QUERY_PLAN = "query_plan"
    PLAN_VERSION = "plan_version"
    PROMPT_TEMPLATE = "prompt_template"


class EdgeType(str, Enum):
    RELATED = "related"
    PARENT = "parent"
    EXAMPLE_OF = "example_of"
    SHARED_TAG = "shared_tag"
    SIMILAR = "similar"


class TenantRole(str, Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class KnowledgeStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Visibility(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


class StagingStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StagingAction(str, Enum):
    NEW = "new"
    MERGE = "merge"
    ADD_VARIANT = "add_variant"


class VariantSource(str, Enum):
    MANUAL = "manual"
    PIPELINE = "pipeline"
    IMPORT = "import"
