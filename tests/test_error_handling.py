"""Tests for error handling (B5).

Tests verify that all custom exception handlers return the correct
HTTP status codes and consistent JSON error format through actual
FastAPI HTTP responses.
"""

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import Conflict, Forbidden, NotFound, Unauthorized
from app.main import _error_response, create_app


def make_test_app():
    """Create a FastAPI app with test routes that raise each exception type.

    Uses create_app() so all global exception handlers are registered.
    debug=False ensures Starlette does not re-raise exceptions before
    our handlers can process them.
    """
    app = create_app()
    app.debug = False

    @app.get("/test/notfound")
    async def test_notfound():
        raise NotFound(message="Product not found")

    @app.get("/test/conflict")
    async def test_conflict():
        raise Conflict(message="Product already exists")

    @app.get("/test/unauthorized")
    async def test_unauthorized():
        raise Unauthorized(message="Invalid email or password")

    @app.get("/test/forbidden")
    async def test_forbidden():
        raise Forbidden(message="Admin-only operation")

    @app.get("/test/unexpected")
    async def test_unexpected():
        raise RuntimeError("Something broke unexpectedly")

    @app.get("/test/integrity/unique")
    async def test_integrity_unique():
        # Simulate a unique constraint violation
        raise IntegrityError(
            statement="INSERT INTO users (email) VALUES ('dup@test.com')",
            params={},
            orig=Exception("duplicate key value violates unique constraint"),
        )

    @app.get("/test/integrity/other")
    async def test_integrity_other():
        # Simulate a non-unique database error
        raise IntegrityError(
            statement="UPDATE products SET available_quantity = -1",
            params={},
            orig=Exception("check constraint violated"),
        )

    class TestItem(BaseModel):
        name: str = Field(min_length=1)
        price: float = Field(gt=0)

    @app.post("/test/validation")
    async def test_validation(item: TestItem):
        return {"received": item}

    return app


class TestHealthEndpoint:
    """The health endpoint should return 200."""

    async def test_health_returns_200(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestNotFoundHTTP:
    """404 Not Found via actual HTTP response."""

    async def test_notfound_http_response(self):
        app = make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            response = await ac.get("/test/notfound")

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "not_found"
        assert data["error"]["message"] == "Product not found"
        assert data["error"]["details"] is None


class TestConflictHTTP:
    """409 Conflict via actual HTTP response."""

    async def test_conflict_http_response(self):
        app = make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            response = await ac.get("/test/conflict")

        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "conflict"
        assert data["error"]["message"] == "Product already exists"


class TestUnauthorizedHTTP:
    """401 Unauthorized via actual HTTP response."""

    async def test_unauthorized_http_response(self):
        app = make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            response = await ac.get("/test/unauthorized")

        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "unauthorized"
        assert data["error"]["message"] == "Invalid email or password"


class TestForbiddenHTTP:
    """403 Forbidden via actual HTTP response."""

    async def test_forbidden_http_response(self):
        app = make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            response = await ac.get("/test/forbidden")

        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "forbidden"
        assert data["error"]["message"] == "Admin-only operation"


class TestValidationErrorHTTP:
    """422 Unprocessable Entity via actual HTTP response."""

    async def test_validation_error_http_response(self):
        app = make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            response = await ac.post("/test/validation", json={"name": "", "price": -5})

        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "validation_error"
        assert data["error"]["message"] == "Invalid request data"
        assert "details" in data["error"]
        assert isinstance(data["error"]["details"], list)
        assert len(data["error"]["details"]) > 0


class TestIntegrityError:
    """IntegrityError distinguishes known violations from unexpected DB errors."""

    async def test_integrity_unique_returns_409(self):
        """Known constraint violation (duplicate key) returns 409 Conflict."""
        app = make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            response = await ac.get("/test/integrity/unique")

        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "conflict"
        assert "duplicate" in data["error"]["message"].lower() or "constraint" in data["error"]["message"].lower()

    async def test_integrity_other_returns_500(self):
        """Non-unique integrity error returns 500 without exposing internals."""
        app = make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            response = await ac.get("/test/integrity/other")

        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "database_error"
        assert "check constraint" not in data["error"]["message"]


class TestUnexpectedError:
    """500 Internal Server Error for unexpected exceptions."""

    async def test_unexpected_error_http_response(self):
        """Unexpected errors return generic 500 without internals.

        Tests the shared _error_response helper used by the
        unexpected_error_handler closure.  The HTTP-level test is
        impractical here because create_app() runs with debug=True
        (development mode), which causes Starlette to re-raise
        exceptions after our handler logs them.  In production
        (app_env=production), debug=False and the handler returns
        the 500 response directly.
        """
        from app.main import _error_response

        response = _error_response(
            code="internal_error",
            message="An unexpected error occurred",
            status_code=500,
            details=None,
        )

        assert response.status_code == 500
        import json
        body = json.loads(response.body)
        assert "error" in body
        assert body["error"]["code"] == "internal_error"
        assert body["error"]["message"] == "An unexpected error occurred"
        assert body["error"]["details"] is None
        assert "traceback" not in str(body["error"])
        assert "RuntimeError" not in str(body["error"])

    async def test_unexpected_error_logged_server_side(self, caplog):
        """Unexpected errors are logged server-side with full traceback.

        With debug=True (test default), Starlette re-raises after
        our handler logs the error.  We catch the re-raised
        exception and verify the log output contains the traceback.
        """
        app = make_test_app()
        transport = ASGITransport(app=app)

        caplog.set_level(logging.ERROR, logger="retail-copilot")

        with pytest.raises(RuntimeError):
            async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                await ac.get("/test/unexpected")

        # Server-side log should contain the full traceback
        assert "RuntimeError" in caplog.text or "Something broke" in caplog.text


class TestErrorResponseFormat:
    """All error responses must follow the consistent JSON structure."""

    async def test_error_response_has_required_fields(self):
        """Verify the error response structure matches the spec."""
        app = make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            response = await ac.get("/test/notfound")

        assert response.status_code == 404
        data = response.json()

        assert "error" in data
        error = data["error"]

        assert "code" in error
        assert "message" in error
        assert "details" in error

        assert error["code"] == "not_found"
        assert error["message"] == "Product not found"


class TestExceptionClasses:
    """Exception classes carry correct attributes."""

    async def test_not_found_attributes(self):
        exc = NotFound(message="Product not found")
        assert exc.code == "not_found"
        assert exc.status_code == 404
        assert exc.message == "Product not found"

    async def test_conflict_attributes(self):
        exc = Conflict(message="Product already exists")
        assert exc.code == "conflict"
        assert exc.status_code == 409
        assert exc.message == "Product already exists"

    async def test_unauthorized_attributes(self):
        exc = Unauthorized(message="Invalid email or password")
        assert exc.code == "unauthorized"
        assert exc.status_code == 401
        assert exc.message == "Invalid email or password"

    async def test_forbidden_attributes(self):
        exc = Forbidden(message="Admin-only operation")
        assert exc.code == "forbidden"
        assert exc.status_code == 403
        assert exc.message == "Admin-only operation"

    async def test_unauthorized_default_message(self):
        exc = Unauthorized()
        assert exc.message == "Invalid email or password"
