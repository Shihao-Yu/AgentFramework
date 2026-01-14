"""Auth models for user context and permissions."""

from enum import Enum
from typing import FrozenSet, Optional

from pydantic import BaseModel, ConfigDict, Field


class Permission(str, Enum):
    """User permissions for authorization."""

    ADMIN = "Admin"
    SUPER_USER = "SuperUser"
    BUYER = "Buyer"
    PLANNER = "Planner"
    PO_CREATE = "POCreate"
    PO_APPROVE = "POApprove"
    PO_VIEW = "POView"
    INVOICE_CREATE = "InvoiceCreate"
    INVOICE_APPROVE = "InvoiceApprove"
    INVOICE_VIEW = "InvoiceView"
    PAYMENT_CREATE = "PaymentCreate"
    PAYMENT_APPROVE = "PaymentApprove"
    HR_VIEW = "HRView"
    HR_ADMIN = "HRAdmin"
    READ = "Read"
    WRITE = "Write"


class Locale(BaseModel):
    """User locale settings."""

    model_config = ConfigDict(frozen=True)

    timezone: str = "UTC"
    language: str = "en-US"
    date_format: str = "MM/DD/YYYY"
    number_format: str = "en-US"
    currency: str = "USD"


class EntityContext(BaseModel):
    """Entity/company context."""

    model_config = ConfigDict(frozen=True)

    entity_id: int
    entity_name: str
    entity_code: Optional[str] = None


class PageContext(BaseModel):
    """Page/module context from UI."""

    model_config = ConfigDict(frozen=True)

    module: str
    page: Optional[str] = None
    object_id: Optional[str] = None
    object_type: Optional[str] = None


class EnrichedUser(BaseModel):
    """Enriched user with permissions and context."""

    model_config = ConfigDict(frozen=True)

    user_id: int
    username: str
    email: str
    display_name: str

    department: str = ""
    title: str = ""
    entity_id: int
    entity_name: str

    is_admin: bool = False
    is_buyer: bool = False
    is_planner: bool = False
    is_super_user: bool = False

    permissions: FrozenSet[Permission] = Field(default_factory=frozenset)
    token: str = Field(default="", exclude=True, repr=False)

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        if self.is_admin or self.is_super_user:
            return True
        return permission in self.permissions

    def has_any_permission(self, *permissions: Permission) -> bool:
        """Check if user has any of the specified permissions."""
        if self.is_admin or self.is_super_user:
            return True
        return any(p in self.permissions for p in permissions)

    def has_all_permissions(self, *permissions: Permission) -> bool:
        """Check if user has all of the specified permissions."""
        if self.is_admin or self.is_super_user:
            return True
        return all(p in self.permissions for p in permissions)

    @classmethod
    def from_jwt_claims(cls, claims: dict, token: str) -> "EnrichedUser":
        """Create EnrichedUser from JWT claims.
        
        Args:
            claims: Decoded JWT claims
            token: Original JWT token
            
        Returns:
            EnrichedUser instance
        """
        # Parse permissions from claims
        raw_permissions = claims.get("permissions", [])
        permissions = frozenset(
            Permission(p) for p in raw_permissions 
            if p in [e.value for e in Permission]
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
            is_buyer=claims.get("is_buyer", False),
            is_planner=claims.get("is_planner", False),
            is_super_user=claims.get("is_super_user", False),
            permissions=permissions,
            token=token,
        )

    @classmethod
    def anonymous(cls) -> "EnrichedUser":
        """Create an anonymous user with no permissions."""
        return cls(
            user_id=0,
            username="anonymous",
            email="",
            display_name="Anonymous User",
            entity_id=0,
            entity_name="",
            permissions=frozenset(),
        )

    @classmethod
    def system(cls) -> "EnrichedUser":
        """Create a system user with all permissions."""
        return cls(
            user_id=-1,
            username="system",
            email="system@internal",
            display_name="System",
            entity_id=0,
            entity_name="System",
            is_admin=True,
            is_super_user=True,
            permissions=frozenset(Permission),
        )
