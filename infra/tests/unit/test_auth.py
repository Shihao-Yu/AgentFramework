import pytest

from infra.auth import EnrichedUser, ResourceAction, RequestContext, Locale


class TestResourceAction:
    def test_create(self):
        action = ResourceAction(resource="purchase_order", action="create")
        assert action.resource == "purchase_order"
        assert action.action == "create"

    def test_from_string(self):
        action = ResourceAction.from_string("invoice:approve")
        assert action.resource == "invoice"
        assert action.action == "approve"

    def test_from_string_invalid(self):
        with pytest.raises(ValueError):
            ResourceAction.from_string("invalid")

    def test_str(self):
        action = ResourceAction(resource="po", action="view")
        assert str(action) == "po:view"

    def test_hash(self):
        action1 = ResourceAction(resource="po", action="create")
        action2 = ResourceAction(resource="po", action="create")
        assert hash(action1) == hash(action2)

    def test_equality(self):
        action1 = ResourceAction(resource="po", action="create")
        action2 = ResourceAction(resource="po", action="create")
        action3 = ResourceAction(resource="po", action="delete")
        assert action1 == action2
        assert action1 != action3


class TestEnrichedUser:
    def test_create(self):
        user = EnrichedUser(
            user_id=1,
            username="test",
            email="test@example.com",
            display_name="Test User",
        )
        assert user.user_id == 1
        assert user.username == "test"

    def test_can_admin(self):
        user = EnrichedUser(
            user_id=1,
            username="admin",
            email="admin@example.com",
            display_name="Admin",
            is_admin=True,
        )
        assert user.can("anything", "whatever") is True

    def test_can_with_permission(self):
        user = EnrichedUser(
            user_id=1,
            username="user",
            email="user@example.com",
            display_name="User",
            resource_actions=frozenset([
                ResourceAction(resource="po", action="create"),
                ResourceAction(resource="po", action="view"),
            ]),
        )
        assert user.can("po", "create") is True
        assert user.can("po", "view") is True
        assert user.can("po", "delete") is False

    def test_can_any(self):
        user = EnrichedUser(
            user_id=1,
            username="user",
            email="user@example.com",
            display_name="User",
            resource_actions=frozenset([
                ResourceAction(resource="po", action="view"),
            ]),
        )
        assert user.can_any(("po", "view"), ("po", "create")) is True
        assert user.can_any(("po", "create"), ("po", "delete")) is False

    def test_can_all(self):
        user = EnrichedUser(
            user_id=1,
            username="user",
            email="user@example.com",
            display_name="User",
            resource_actions=frozenset([
                ResourceAction(resource="po", action="view"),
                ResourceAction(resource="po", action="create"),
            ]),
        )
        assert user.can_all(("po", "view"), ("po", "create")) is True
        assert user.can_all(("po", "view"), ("po", "delete")) is False

    def test_anonymous(self):
        user = EnrichedUser.anonymous()
        assert user.user_id == 0
        assert user.username == "anonymous"
        assert user.can("po", "view") is False

    def test_system(self):
        user = EnrichedUser.system()
        assert user.user_id == -1
        assert user.is_admin is True
        assert user.can("anything", "whatever") is True

    def test_from_jwt_claims(self):
        claims = {
            "user_id": 42,
            "username": "jdoe",
            "email": "jdoe@example.com",
            "name": "John Doe",
            "resource_actions": ["po:create", "po:view", "invalid"],
        }
        user = EnrichedUser.from_jwt_claims(claims, "token123")
        assert user.user_id == 42
        assert user.username == "jdoe"
        assert user.can("po", "create") is True
        assert user.can("po", "view") is True


class TestRequestContext:
    def test_create(self):
        user = EnrichedUser.anonymous()
        ctx = RequestContext.create(user=user, session_id="sess-1")
        assert ctx.user == user
        assert ctx.session_id == "sess-1"
        assert ctx.request_id is not None

    def test_for_system(self):
        ctx = RequestContext.for_system()
        assert ctx.user.is_admin is True
        assert ctx.session_id == "system"

    def test_for_anonymous(self):
        ctx = RequestContext.for_anonymous(session_id="anon-123")
        assert ctx.user.user_id == 0
        assert ctx.session_id == "anon-123"

    def test_with_extra(self):
        user = EnrichedUser.anonymous()
        ctx = RequestContext.create(user=user)
        ctx2 = ctx.with_extra(foo="bar", baz=123)
        assert ctx.extra == {}
        assert ctx2.extra == {"foo": "bar", "baz": 123}

    def test_current_context(self):
        user = EnrichedUser.anonymous()
        ctx = RequestContext.create(user=user, session_id="test")
        ctx.set_current()

        current = RequestContext.current()
        assert current == ctx

        RequestContext.clear_current()
        assert RequestContext.current() is None

    def test_require_current_raises(self):
        RequestContext.clear_current()
        with pytest.raises(RuntimeError):
            RequestContext.require_current()


class TestLocale:
    def test_defaults(self):
        locale = Locale()
        assert locale.timezone == "UTC"
        assert locale.language == "en-US"
        assert locale.currency == "USD"
