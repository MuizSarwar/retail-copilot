"""Authentication tests (B10, Part 1).

Tests cover registration, login, and current user endpoints
against the actual FastAPI application.

Uses unique email addresses per test to avoid conflicts
between test runs (since commits now persist to the database).
"""

import time
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import engine
from app.main import create_app


def unique_email(base: str) -> str:
    """Generate a unique email address using a timestamp suffix."""
    return f"{base}.{int(time.time() * 1000)}@test.com"


async def create_user_via_repo(email: str, password: str, role_name: str):
    """Create a user directly via UserRepository (for test setup only).

    Bypasses the API to create users with specific roles, including admin.
    """
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.modules.auth.repositories.user_repository import UserRepository

    async with SessionLocal() as session:
        repo = UserRepository(session=session)
        role = await repo.get_role_by_name(role_name)
        if role is None:
            raise RuntimeError(f"Role '{role_name}' not found in database")
        user = await repo.create(email, hash_password(password), role.id)
        await session.commit()
        await session.refresh(user)
        return user


async def login_and_get_token(app_client, email: str, password: str) -> str:
    """Helper to login and return the JWT access token."""
    login_resp = await app_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return login_resp.json()["access_token"]


@pytest.fixture
async def app_client():
    """Create a test client with the full FastAPI app.

    Includes the test-only authorization router so authorization tests
    can exercise /test/admin-only and /test/employee-or-admin routes.
    Disposes the database engine after each test to avoid connection
    pool corruption.
    """
    from tests.auth_test_routes import router as test_auth_router

    app = create_app()
    app.include_router(test_auth_router, prefix="/api/v1/auth")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


class TestRegistration:
    """POST /api/v1/auth/register"""

    async def test_successful_employee_registration(self, app_client):
        """Registering a new employee returns 201."""
        email = unique_email("newuser")
        response = await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == email
        assert data["role"] == "employee"
        assert data["is_active"] is True
        assert "password_hash" not in data

    async def test_duplicate_email_returns_409(self, app_client):
        """Registering with an existing email returns 409."""
        email = unique_email("dup")
        # First registration
        await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        # Second registration with same email
        response = await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "conflict"

    async def test_registration_always_creates_employee(self, app_client):
        """Public registration always creates an employee role."""
        email = unique_email("role")
        response = await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "employee"

    async def test_registration_no_password_hash_in_response(self, app_client):
        """Password hash must never appear in API response."""
        email = unique_email("nohash")
        response = await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "password_hash" not in data
        assert "password" not in data

    async def test_registration_validation_error(self, app_client):
        """Invalid input returns 422."""
        response = await app_client.post(
            "/api/v1/auth/register",
            json={"email": "invalid-email", "password": "short"},
        )
        assert response.status_code == 422


class TestLogin:
    """POST /api/v1/auth/login"""

    async def test_successful_login_returns_jwt(self, app_client):
        """Valid credentials return 200 with JWT."""
        email = unique_email("login")
        # Register first
        await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        # Login
        response = await app_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecurePass123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    async def test_login_wrong_email_returns_401(self, app_client):
        """Wrong email returns 401."""
        email = unique_email("exists")
        await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        response = await app_client.post(
            "/api/v1/auth/login",
            json={"email": unique_email("nonexistent"), "password": "SecurePass123!"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "unauthorized"

    async def test_login_wrong_password_returns_401(self, app_client):
        """Wrong password returns 401."""
        email = unique_email("pass")
        await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        response = await app_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword!"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "unauthorized"

    async def test_login_same_error_for_wrong_email_and_password(self, app_client):
        """Wrong email and wrong password return identical responses."""
        email = unique_email("same")
        await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        # Wrong email
        resp1 = await app_client.post(
            "/api/v1/auth/login",
            json={"email": unique_email("wrong"), "password": "SecurePass123!"},
        )
        # Wrong password
        resp2 = await app_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword!"},
        )
        assert resp1.status_code == resp2.status_code == 401
        assert resp1.json() == resp2.json()

    async def test_login_no_password_hash_in_response(self, app_client):
        """Login response never includes password hash."""
        email = unique_email("nohash2")
        await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        response = await app_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecurePass123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "password_hash" not in data
        assert "password" not in data
        assert "access_token" in data


class TestCurrentUser:
    """GET /api/v1/auth/me"""

    async def test_get_me_with_valid_token(self, app_client):
        """Valid Bearer token returns 200 with user info."""
        email = unique_email("me")
        # Register and login
        await app_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        login_resp = await app_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecurePass123!"},
        )
        token = login_resp.json()["access_token"]

        # Get current user
        response = await app_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["role"] == "employee"
        assert "password_hash" not in data

    async def test_get_me_without_token_returns_401(self, app_client):
        """Missing token returns 401."""
        response = await app_client.get("/api/v1/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "unauthorized"

    async def test_get_me_with_invalid_token_returns_401(self, app_client):
        """Invalid token returns 401."""
        response = await app_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "unauthorized"

    async def test_get_me_with_expired_token_returns_401(self, app_client):
        """Expired token returns 401."""
        import jwt
        from datetime import datetime, timedelta, timezone

        # Create an expired token
        now = datetime.now(timezone.utc)
        expired = now - timedelta(minutes=5)
        payload = {"sub": "1", "exp": expired, "iat": expired}
        token = jwt.encode(
            payload, "any-secret", algorithm="HS256"
        )

        response = await app_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "unauthorized"

    async def test_get_me_with_inactive_user_returns_401(self, app_client):
        """Inactive user returns 401 even with a valid token."""
        email = unique_email("inactive")
        await create_user_via_repo(email, "SecurePass123!", "employee")
        token = await login_and_get_token(app_client, email, "SecurePass123!")

        # Deactivate the user directly in the database
        from app.core.database import SessionLocal
        from app.modules.auth.models.user import User
        from sqlalchemy import update

        async with SessionLocal() as session:
            await session.execute(update(User).where(User.email == email).values(is_active=False))
            await session.commit()

        response = await app_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "unauthorized"

    async def test_role_change_takes_effect_immediately(self, app_client):
        """Changing a user's role in the database immediately changes permissions.

        The role is loaded from PostgreSQL on every request, not from JWT claims,
        so a role change takes effect without issuing a new token.
        """
        email = unique_email("role-change")
        await create_user_via_repo(email, "SecurePass123!", "employee")
        token = await login_and_get_token(app_client, email, "SecurePass123!")

        # As an employee, admin-only route should return 403
        response = await app_client.get(
            "/api/v1/auth/test/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

        # Change the user's role to admin directly in the database
        from app.core.database import SessionLocal
        from app.modules.auth.models.role import Role
        from app.modules.auth.models.user import User
        from sqlalchemy import select, update

        async with SessionLocal() as session:
            admin_role = await session.execute(select(Role).where(Role.name == "admin"))
            admin_role_id = admin_role.scalar_one().id
            await session.execute(update(User).where(User.email == email).values(role_id=admin_role_id))
            await session.commit()

        # With the SAME token, the admin-only route should now return 200
        response = await app_client.get(
            "/api/v1/auth/test/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"


class TestAuthorization:
    """Role-based authorization tests (B10, Part 2).

    Tests that admin-only routes block employees (403) and allow admins (200).
    Uses temporary test routes under /api/v1/auth/test/ that exist only for
    authorization verification — these will be removed when real domain
    endpoints are implemented in later parts.
    """

    # ---------------------------------------------------------------
    # Employee blocked from admin-only route
    # ---------------------------------------------------------------

    async def test_employee_blocked_from_admin_route(self, app_client):
        """An employee cannot access an admin-only route (403)."""
        email = unique_email("emp-blocked")
        await create_user_via_repo(email, "SecurePass123!", "employee")
        token = await login_and_get_token(app_client, email, "SecurePass123!")

        response = await app_client.get(
            "/api/v1/auth/test/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "forbidden"

    async def test_employee_allowed_on_employee_or_admin_route(self, app_client):
        """An employee CAN access the employee-or-admin route (200)."""
        email = unique_email("emp-allowed")
        await create_user_via_repo(email, "SecurePass123!", "employee")
        token = await login_and_get_token(app_client, email, "SecurePass123!")

        response = await app_client.get(
            "/api/v1/auth/test/employee-or-admin",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "employee"

    # ---------------------------------------------------------------
    # Admin allowed on admin-only route
    # ---------------------------------------------------------------

    async def test_admin_allowed_on_admin_route(self, app_client):
        """An admin can access an admin-only route (200)."""
        email = unique_email("admin-ok")
        await create_user_via_repo(email, "SecurePass123!", "admin")
        token = await login_and_get_token(app_client, email, "SecurePass123!")

        response = await app_client.get(
            "/api/v1/auth/test/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert data["message"] == "Admin access granted"

    async def test_admin_allowed_on_employee_or_admin_route(self, app_client):
        """An admin can also access the employee-or-admin route (200)."""
        email = unique_email("admin-both")
        await create_user_via_repo(email, "SecurePass123!", "admin")
        token = await login_and_get_token(app_client, email, "SecurePass123!")

        response = await app_client.get(
            "/api/v1/auth/test/employee-or-admin",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
