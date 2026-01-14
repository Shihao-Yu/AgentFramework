"""Unit tests for auth module."""

import pytest

from agentcore.auth.models import Permission, EnrichedUser, Locale, EntityContext, PageContext
from agentcore.auth.context import RequestContext


class TestPermission:
    def test_permission_values(self):
        assert Permission.ADMIN.value == "Admin"
        assert Permission.BUYER.value == "Buyer"
        assert Permission.PO_CREATE.value == "POCreate"


class TestEnrichedUser:
    @pytest.fixture
    def buyer_user(self):
        return EnrichedUser(
            user_id=123,
            username="buyer1",
            email="buyer1@company.com",
            display_name="Test Buyer",
            entity_id=1,
            entity_name="Acme Corp",
            permissions=frozenset([Permission.BUYER, Permission.PO_CREATE, Permission.PO_VIEW]),
        )

    @pytest.fixture
    def admin_user(self):
        return EnrichedUser(
            user_id=1,
            username="admin",
            email="admin@company.com",
            display_name="Admin User",
            entity_id=1,
            entity_name="Acme Corp",
            is_admin=True,
            permissions=frozenset([Permission.ADMIN]),
        )

    def test_has_permission_granted(self, buyer_user):
        assert buyer_user.has_permission(Permission.BUYER) is True
        assert buyer_user.has_permission(Permission.PO_CREATE) is True

    def test_has_permission_denied(self, buyer_user):
        assert buyer_user.has_permission(Permission.ADMIN) is False
        assert buyer_user.has_permission(Permission.INVOICE_CREATE) is False

    def test_admin_has_all_permissions(self, admin_user):
        assert admin_user.has_permission(Permission.BUYER) is True
        assert admin_user.has_permission(Permission.INVOICE_CREATE) is True
        assert admin_user.has_permission(Permission.HR_ADMIN) is True

    def test_has_any_permission(self, buyer_user):
        assert buyer_user.has_any_permission(Permission.BUYER, Permission.ADMIN) is True
        assert buyer_user.has_any_permission(Permission.ADMIN, Permission.HR_ADMIN) is False

    def test_has_all_permissions(self, buyer_user):
        assert buyer_user.has_all_permissions(Permission.BUYER, Permission.PO_CREATE) is True
        assert buyer_user.has_all_permissions(Permission.BUYER, Permission.ADMIN) is False

    def test_token_excluded_from_repr(self, buyer_user):
        user_with_token = EnrichedUser(
            user_id=123,
            username="test",
            email="test@test.com",
            display_name="Test",
            entity_id=1,
            entity_name="Test",
            token="super-secret-token",
        )
        
        repr_str = repr(user_with_token)
        assert "super-secret-token" not in repr_str

    def test_from_jwt_claims(self):
        claims = {
            "user_id": 456,
            "username": "jdoe",
            "email": "jdoe@company.com",
            "name": "Jane Doe",
            "department": "Finance",
            "title": "Manager",
            "entity_id": 2,
            "entity_name": "Globex",
            "is_buyer": True,
            "permissions": ["Buyer", "POCreate", "InvalidPermission"],
        }
        
        user = EnrichedUser.from_jwt_claims(claims, "jwt-token")
        
        assert user.user_id == 456
        assert user.username == "jdoe"
        assert user.is_buyer is True
        assert Permission.BUYER in user.permissions
        assert Permission.PO_CREATE in user.permissions
        assert user.token == "jwt-token"

    def test_anonymous_user(self):
        anon = EnrichedUser.anonymous()
        
        assert anon.user_id == 0
        assert anon.username == "anonymous"
        assert anon.has_permission(Permission.READ) is False
        assert len(anon.permissions) == 0

    def test_system_user(self):
        system = EnrichedUser.system()
        
        assert system.user_id == -1
        assert system.is_admin is True
        assert system.is_super_user is True
        assert system.has_permission(Permission.ADMIN) is True

    def test_immutable(self, buyer_user):
        with pytest.raises(Exception):
            buyer_user.user_id = 999


class TestLocale:
    def test_defaults(self):
        locale = Locale()
        
        assert locale.timezone == "UTC"
        assert locale.language == "en-US"
        assert locale.currency == "USD"

    def test_custom(self):
        locale = Locale(
            timezone="America/New_York",
            language="es-ES",
            currency="EUR",
        )
        
        assert locale.timezone == "America/New_York"
        assert locale.language == "es-ES"
        assert locale.currency == "EUR"


class TestRequestContext:
    @pytest.fixture
    def user(self):
        return EnrichedUser(
            user_id=123,
            username="test",
            email="test@test.com",
            display_name="Test User",
            entity_id=1,
            entity_name="Test Corp",
        )

    def test_create_minimal(self, user):
        ctx = RequestContext.create(user=user, session_id="sess_123")
        
        assert ctx.user.user_id == 123
        assert ctx.session_id == "sess_123"
        assert ctx.request_id is not None
        assert ctx.locale.timezone == "UTC"

    def test_create_full(self, user):
        entity = EntityContext(entity_id=1, entity_name="Acme")
        page = PageContext(module="Purchasing", page="PO List")
        
        ctx = RequestContext.create(
            user=user,
            session_id="sess_123",
            request_id="req_456",
            entity=entity,
            page=page,
            custom_field="value",
        )
        
        assert ctx.session_id == "sess_123"
        assert ctx.request_id == "req_456"
        assert ctx.entity.entity_name == "Acme"
        assert ctx.page.module == "Purchasing"
        assert ctx.extra["custom_field"] == "value"

    def test_contextvars(self, user):
        ctx = RequestContext.create(user=user, session_id="sess_123")
        
        assert RequestContext.current() is None
        
        ctx.set_current()
        
        assert RequestContext.current() is ctx
        assert RequestContext.require_current() is ctx
        
        RequestContext.clear_current()
        
        assert RequestContext.current() is None

    def test_require_current_raises(self):
        RequestContext.clear_current()
        
        with pytest.raises(RuntimeError, match="No request context set"):
            RequestContext.require_current()

    def test_with_extra(self, user):
        ctx = RequestContext.create(user=user, session_id="sess_123", initial="value")
        
        new_ctx = ctx.with_extra(added="new_value")
        
        assert ctx is not new_ctx
        assert new_ctx.extra["initial"] == "value"
        assert new_ctx.extra["added"] == "new_value"

    def test_with_page(self, user):
        ctx = RequestContext.create(user=user, session_id="sess_123")
        page = PageContext(module="Finance", page="Invoice List")
        
        new_ctx = ctx.with_page(page)
        
        assert ctx is not new_ctx
        assert new_ctx.page.module == "Finance"

    def test_for_system(self):
        ctx = RequestContext.for_system()
        
        assert ctx.user.is_admin is True
        assert ctx.user.username == "system"

    def test_for_anonymous(self):
        ctx = RequestContext.for_anonymous()
        
        assert ctx.user.user_id == 0
        assert ctx.user.username == "anonymous"
