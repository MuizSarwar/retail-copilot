"""Custom application errors.

Each exception carries an error code, a user-friendly message,
and an HTTP status code. Services raise these; controllers stay
thin and never catch them directly.
"""

from typing import Any, Optional


class AppError(Exception):
    """Base application error."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        details: Optional[Any] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFound(AppError):
    """Resource not found (HTTP 404)."""

    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(code="not_found", message=message, status_code=404, details=details)


class Conflict(AppError):
    """Resource conflict / duplicate (HTTP 409)."""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(code="conflict", message=message, status_code=409, details=details)


class Unauthorized(AppError):
    """Missing, invalid, or expired authentication (HTTP 401)."""

    def __init__(
        self,
        message: str = "Invalid email or password",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(code="unauthorized", message=message, status_code=401, details=details)


class Forbidden(AppError):
    """Insufficient permissions (HTTP 403)."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(code="forbidden", message=message, status_code=403, details=details)
