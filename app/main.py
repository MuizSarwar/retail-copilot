import logging
import sys
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.exceptions import AppError, Conflict, Forbidden, NotFound, Unauthorized

logger = logging.getLogger("retail-copilot")


def _error_response(code: str, message: str, status_code: int, details: Any = None) -> JSONResponse:
    """Build a consistent error response body."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    All normal API routes are mounted under /api/v1.
    The /mcp endpoint is the only exception (handled later in Part 16).
    """
    app = FastAPI(title=settings.app_name, debug=settings.app_env == "development")

    app.include_router(api_v1_router, prefix="/api/v1")

    # --- Global exception handlers ---

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        """Handle custom application exceptions."""
        return _error_response(exc.code, exc.message, exc.status_code, exc.details)

    @app.exception_handler(NotFound)
    async def not_found_handler(_request: Request, exc: NotFound) -> JSONResponse:
        return _error_response(exc.code, exc.message, exc.status_code, exc.details)

    @app.exception_handler(Conflict)
    async def conflict_handler(_request: Request, exc: Conflict) -> JSONResponse:
        return _error_response(exc.code, exc.message, exc.status_code, exc.details)

    @app.exception_handler(Unauthorized)
    async def unauthorized_handler(_request: Request, exc: Unauthorized) -> JSONResponse:
        return _error_response(exc.code, exc.message, exc.status_code, exc.details)

    @app.exception_handler(Forbidden)
    async def forbidden_handler(_request: Request, exc: Forbidden) -> JSONResponse:
        return _error_response(exc.code, exc.message, exc.status_code, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle FastAPI validation errors with field-level details."""
        details = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error.get("loc", []))
            details.append({"field": field, "message": error.get("msg", "")})
        return _error_response(
            code="validation_error",
            message="Invalid request data",
            status_code=422,
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle Starlette/FastAPI HTTP exceptions.

        Maps common status codes to consistent error codes:
        404 -> not_found, 401 -> unauthorized, 403 -> forbidden, etc.
        """
        code_map = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            409: "conflict",
            422: "validation_error",
            500: "internal_error",
        }
        code = code_map.get(exc.status_code, "http_error")
        return _error_response(
            code=code,
            message=str(exc.detail),
            status_code=exc.status_code,
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        _request: Request, exc: IntegrityError
    ) -> JSONResponse:
        """Translate database integrity violations into application errors.

        Only known constraint violations become 409. Unexpected
        database failures fall through to the generic 500 handler.
        """
        error_message = str(exc.orig) if exc.orig else str(exc)
        lower = error_message.lower()
        if "unique" in lower or "duplicate" in lower or "already exists" in lower:
            return _error_response(
                code="conflict",
                message="Duplicate resource or constraint violation",
                status_code=409,
                details=None,
            )
        # Fall through to generic database error
        logger.error("Database integrity error: %s", error_message)
        return _error_response(
            code="database_error",
            message="A database error occurred",
            status_code=500,
            details=None,
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(
        _request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        """Handle unexpected SQLAlchemy errors without exposing internals."""
        logger.error("SQLAlchemy error: %s", str(exc))
        return _error_response(
            code="database_error",
            message="A database error occurred",
            status_code=500,
            details=None,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Handle all unexpected exceptions.

        Logs the full traceback server-side but returns a generic
        500 to the client. Never exposes stack traces or internals.
        """
        logger.error(
            "Unexpected error: %s\n%s",
            str(exc),
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
        return _error_response(
            code="internal_error",
            message="An unexpected error occurred",
            status_code=500,
            details=None,
        )

    @app.get("/api/v1/health", tags=["health"])
    async def health() -> JSONResponse:
        """Health check endpoint. Returns 200 if the application is running."""
        return JSONResponse({"status": "ok", "app": settings.app_name, "env": settings.app_env})

    return app


app = create_app()


def cli() -> None:
    """Entry point for the `retail-copilot` console script."""
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=settings.app_env == "development")


if __name__ == "__main__":
    try:
        # Force settings validation at import time so missing secrets fail fast
        _ = settings.database_url
        _ = settings.jwt_secret_key
        _ = settings.groq_api_key
    except Exception as exc:  # pydantic ValidationError
        print(f"FATAL: Required configuration is missing: {exc}", file=sys.stderr)
        sys.exit(1)
    cli()
