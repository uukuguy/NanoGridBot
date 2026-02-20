"""Unit tests for RBAC module."""

import pytest

from nanogridbot.types import User, UserRole, Permission, ROLE_PERMISSIONS
from nanogridbot.rbac.permissions import (
    has_permission,
    has_role,
    PermissionChecker,
    require_permission,
)


class TestHasPermission:
    """Test has_permission function."""

    def test_owner_has_all_permissions(self):
        """Test that owner role has all permissions."""
        user = User(id=1, username="owner", password_hash="hash", role=UserRole.OWNER)
        # Owner should have USERS_MANAGE permission
        assert has_permission(user, Permission.USERS_MANAGE) is True

    def test_admin_has_users_manage(self):
        """Test that admin role has users.manage permission."""
        user = User(id=2, username="admin", password_hash="hash", role=UserRole.ADMIN)
        assert has_permission(user, Permission.USERS_MANAGE) is True

    def test_user_does_not_have_users_manage(self):
        """Test that user role does not have users.manage permission."""
        user = User(id=3, username="user", password_hash="hash", role=UserRole.USER)
        assert has_permission(user, Permission.USERS_MANAGE) is False

    def test_user_has_groups_create(self):
        """Test that user role has groups.create permission."""
        user = User(id=3, username="user", password_hash="hash", role=UserRole.USER)
        assert has_permission(user, Permission.GROUPS_CREATE) is True

    def test_viewer_has_groups_view(self):
        """Test that viewer role has groups.view permission."""
        user = User(id=4, username="viewer", password_hash="hash", role=UserRole.VIEWER)
        assert has_permission(user, Permission.GROUPS_VIEW) is True

    def test_viewer_does_not_have_groups_create(self):
        """Test that viewer role does not have groups.create permission."""
        user = User(id=4, username="viewer", password_hash="hash", role=UserRole.VIEWER)
        assert has_permission(user, Permission.GROUPS_CREATE) is False

    def test_guest_has_limited_permissions(self):
        """Test that guest role has minimal permissions."""
        user = User(id=5, username="guest", password_hash="hash", role=UserRole.GUEST)
        # Guest can only view containers and tasks
        assert has_permission(user, Permission.CONTAINERS_VIEW) is True
        assert has_permission(user, Permission.TASKS_VIEW) is True
        assert has_permission(user, Permission.GROUPS_CREATE) is False


class TestHasRole:
    """Test has_role function."""

    def test_owner_meets_owner_requirement(self):
        """Test that owner meets owner requirement."""
        user = User(id=1, username="owner", password_hash="hash", role=UserRole.OWNER)
        assert has_role(user, UserRole.OWNER) is True

    def test_admin_meets_user_requirement(self):
        """Test that admin meets user requirement."""
        user = User(id=2, username="admin", password_hash="hash", role=UserRole.ADMIN)
        assert has_role(user, UserRole.USER) is True

    def test_user_does_not_meet_admin_requirement(self):
        """Test that user does not meet admin requirement."""
        user = User(id=3, username="user", password_hash="hash", role=UserRole.USER)
        assert has_role(user, UserRole.ADMIN) is False

    def test_viewer_meets_guest_requirement(self):
        """Test that viewer meets guest requirement."""
        user = User(id=4, username="viewer", password_hash="hash", role=UserRole.VIEWER)
        assert has_role(user, UserRole.GUEST) is True

    def test_guest_does_not_meet_viewer_requirement(self):
        """Test that guest does not meet viewer requirement."""
        user = User(id=5, username="guest", password_hash="hash", role=UserRole.GUEST)
        assert has_role(user, UserRole.VIEWER) is False


class TestPermissionChecker:
    """Test PermissionChecker class."""

    def test_owner_permissions_count(self):
        """Test that owner has expected number of permissions."""
        user = User(id=1, username="owner", password_hash="hash", role=UserRole.OWNER)
        checker = PermissionChecker(user)
        # Owner should have 15 permissions
        assert len(checker.permissions) == 15

    def test_admin_permissions_count(self):
        """Test that admin has expected number of permissions."""
        user = User(id=2, username="admin", password_hash="hash", role=UserRole.ADMIN)
        checker = PermissionChecker(user)
        # Admin should have 15 permissions (same as owner in current implementation)
        assert len(checker.permissions) == 15

    def test_user_permissions_count(self):
        """Test that user has expected number of permissions."""
        user = User(id=3, username="user", password_hash="hash", role=UserRole.USER)
        checker = PermissionChecker(user)
        # User should have 9 permissions
        assert len(checker.permissions) == 9

    def test_can_method(self):
        """Test can() method."""
        user = User(id=1, username="owner", password_hash="hash", role=UserRole.OWNER)
        checker = PermissionChecker(user)
        assert checker.can(Permission.USERS_MANAGE) is True
        assert checker.can(Permission.GROUPS_CREATE) is True

    def test_can_method_denies(self):
        """Test can() method denies correctly."""
        user = User(id=5, username="guest", password_hash="hash", role=UserRole.GUEST)
        checker = PermissionChecker(user)
        assert checker.can(Permission.USERS_MANAGE) is False

    def test_can_any_method(self):
        """Test can_any() method."""
        user = User(id=3, username="user", password_hash="hash", role=UserRole.USER)
        checker = PermissionChecker(user)
        assert checker.can_any(Permission.GROUPS_CREATE, Permission.USERS_MANAGE) is True

    def test_can_any_method_all_false(self):
        """Test can_any() method when all false."""
        user = User(id=5, username="guest", password_hash="hash", role=UserRole.GUEST)
        checker = PermissionChecker(user)
        assert checker.can_any(Permission.USERS_MANAGE, Permission.USERS_INVITE) is False

    def test_can_all_method(self):
        """Test can_all() method."""
        user = User(id=3, username="user", password_hash="hash", role=UserRole.USER)
        checker = PermissionChecker(user)
        assert checker.can_all(Permission.GROUPS_CREATE, Permission.GROUPS_VIEW) is True

    def test_can_all_method_one_false(self):
        """Test can_all() method when one is false."""
        user = User(id=3, username="user", password_hash="hash", role=UserRole.USER)
        checker = PermissionChecker(user)
        assert checker.can_all(Permission.GROUPS_CREATE, Permission.USERS_MANAGE) is False

    def test_is_at_least_method(self):
        """Test is_at_least() method."""
        user = User(id=2, username="admin", password_hash="hash", role=UserRole.ADMIN)
        checker = PermissionChecker(user)
        assert checker.is_at_least(UserRole.USER) is True
        assert checker.is_at_least(UserRole.ADMIN) is True
        assert checker.is_at_least(UserRole.OWNER) is False

    def test_permissions_cached(self):
        """Test that permissions are cached."""
        user = User(id=1, username="owner", password_hash="hash", role=UserRole.OWNER)
        checker = PermissionChecker(user)
        _ = checker.permissions
        # Modify the cached permissions
        checker._permissions.add(Permission.USERS_MANAGE)
        # Should still have the permission
        assert Permission.USERS_MANAGE in checker.permissions


class TestRequirePermissionDecorator:
    """Test require_permission decorator."""

    @pytest.mark.asyncio
    async def test_decorator_allows_permission(self):
        """Test decorator allows when user has permission."""
        user = User(id=1, username="owner", password_hash="hash", role=UserRole.OWNER)

        @require_permission(Permission.USERS_MANAGE)
        async def test_func(user: User):
            return "success"

        result = await test_func(user=user)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_denies_permission(self):
        """Test decorator denies when user lacks permission."""
        user = User(id=3, username="user", password_hash="hash", role=UserRole.USER)

        @require_permission(Permission.USERS_MANAGE)
        async def test_func(user: User):
            return "success"

        with pytest.raises(PermissionError) as exc_info:
            await test_func(user=user)
        assert "Permission denied" in str(exc_info.value)

    def test_decorator_sync_function(self):
        """Test decorator with sync function."""
        user = User(id=1, username="owner", password_hash="hash", role=UserRole.OWNER)

        @require_permission(Permission.USERS_MANAGE)
        def test_func(user: User):
            return "success"

        result = test_func(user=user)
        assert result == "success"

    def test_decorator_sync_denies(self):
        """Test decorator denies sync function without permission."""
        user = User(id=5, username="guest", password_hash="hash", role=UserRole.GUEST)

        @require_permission(Permission.USERS_MANAGE)
        def test_func(user: User):
            return "success"

        with pytest.raises(PermissionError):
            test_func(user=user)


class TestRolePermissions:
    """Test ROLE_PERMISSIONS mapping."""

    def test_all_roles_have_permissions(self):
        """Test that all roles have defined permissions."""
        for role in UserRole:
            assert role in ROLE_PERMISSIONS
            assert len(ROLE_PERMISSIONS[role]) > 0

    def test_owner_has_most_permissions(self):
        """Test that owner has the most permissions."""
        owner_perms = len(ROLE_PERMISSIONS[UserRole.OWNER])
        guest_perms = len(ROLE_PERMISSIONS[UserRole.GUEST])
        assert owner_perms > guest_perms

    def test_permissions_are_permission_type(self):
        """Test that all permissions are Permission enum values."""
        for role, perms in ROLE_PERMISSIONS.items():
            for perm in perms:
                assert isinstance(perm, Permission)
