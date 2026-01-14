from typing import FrozenSet, Optional

from pydantic import BaseModel, ConfigDict, Field


class ResourceAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource: str
    action: str

    def __hash__(self) -> int:
        return hash((self.resource, self.action))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ResourceAction):
            return self.resource == other.resource and self.action == other.action
        return False

    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"

    @classmethod
    def from_string(cls, s: str) -> "ResourceAction":
        parts = s.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid resource action format: {s}")
        return cls(resource=parts[0], action=parts[1])


class Locale(BaseModel):
    model_config = ConfigDict(frozen=True)

    timezone: str = "UTC"
    language: str = "en-US"
    date_format: str = "MM/DD/YYYY"
    number_format: str = "en-US"
    currency: str = "USD"


class EntityContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_id: int
    entity_name: str
    entity_code: Optional[str] = None


class PageContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    module: str
    page: Optional[str] = None
    object_id: Optional[str] = None
    object_type: Optional[str] = None


class EnrichedUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: int
    username: str
    email: str
    display_name: str

    department: str = ""
    title: str = ""
    entity_id: int = 0
    entity_name: str = ""

    is_admin: bool = False
    is_super_user: bool = False

    resource_actions: FrozenSet[ResourceAction] = Field(default_factory=frozenset)
    token: str = Field(default="", exclude=True, repr=False)

    def can(self, resource: str, action: str) -> bool:
        if self.is_admin or self.is_super_user:
            return True
        return ResourceAction(resource=resource, action=action) in self.resource_actions

    def can_any(self, *resource_actions: tuple[str, str]) -> bool:
        if self.is_admin or self.is_super_user:
            return True
        return any(
            ResourceAction(resource=r, action=a) in self.resource_actions
            for r, a in resource_actions
        )

    def can_all(self, *resource_actions: tuple[str, str]) -> bool:
        if self.is_admin or self.is_super_user:
            return True
        return all(
            ResourceAction(resource=r, action=a) in self.resource_actions
            for r, a in resource_actions
        )

    @classmethod
    def from_jwt_claims(cls, claims: dict, token: str) -> "EnrichedUser":
        raw_actions = claims.get("resource_actions", [])
        resource_actions = frozenset(
            ResourceAction.from_string(a) for a in raw_actions if ":" in a
        )

        return cls(
            user_id=claims.get("user_id", claims.get("sub", 0)),
            username=claims.get("username", claims.get("preferred_username", "")),
            email=claims.get("email", ""),
            display_name=claims.get("name", claims.get("display_name", "")),
            department=claims.get("department", ""),
            title=claims.get("title", ""),
            entity_id=claims.get("entity_id", 0),
            entity_name=claims.get("entity_name", ""),
            is_admin=claims.get("is_admin", False),
            is_super_user=claims.get("is_super_user", False),
            resource_actions=resource_actions,
            token=token,
        )

    @classmethod
    def anonymous(cls) -> "EnrichedUser":
        return cls(
            user_id=0,
            username="anonymous",
            email="",
            display_name="Anonymous User",
            resource_actions=frozenset(),
        )

    @classmethod
    def system(cls) -> "EnrichedUser":
        return cls(
            user_id=-1,
            username="system",
            email="system@internal",
            display_name="System",
            is_admin=True,
            is_super_user=True,
            resource_actions=frozenset(),
        )
