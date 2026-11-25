import sys

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_v1_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    All normal API routes are mounted under /api/v1.
    The /mcp endpoint is the only exception (handled later in Part 16).
    """
    app = FastAPI(title=settings.app_name, debug=settings.app_env == "development")

    app.include_router(api_v1_router, prefix="/api/v1")

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
