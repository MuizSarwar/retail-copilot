"""Authentication tests (B10, Part 1).

Tests cover registration, login, and current user endpoints
against the actual FastAPI application.

Uses unique email addresses per test to avoid conflicts
between test runs (since commits now persist to the database).
"""

import time
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


def unique_email(base: str) -> str:
    """Generate a unique email address using a timestamp suffix."""
    return f"{base}.{int(time.time() * 1000)}@test.com"


@pytest.fixture
async def app_client():
    """Create a test client with the full FastAPI app."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


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
