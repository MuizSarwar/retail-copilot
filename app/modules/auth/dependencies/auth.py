"""Authentication dependencies — JWT verification and user extraction.

Dependencies used by controllers to authenticate requests and extract
the current user's ID from a Bearer JWT.
"""

from typing import Optional

from fastapi import Depends, Header
import jwt

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import Unauthorized
from app.core.security import verify_access_token
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.auth_service import AuthService


async def get_user_repository(
    db=Depends(get_db),
) -> UserRepository:
    """Create a UserRepository with an active database session."""
    return UserRepository(session=db)


async def get_auth_service(
    repository: UserRepository = Depends(get_user_repository),
) -> AuthService:
    """Create an AuthService with the given repository."""
    return AuthService(repository=repository)


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
) -> int:
    """Extract the user ID from a Bearer JWT token.

    Returns the user ID (sub claim) as an integer.
    Raises Unauthorized if the token is missing, invalid, or expired.
    """
    if authorization is None:
        raise Unauthorized(message="Invalid email or password")

    try:
        scheme, token = authorization.split(" ", 1)
    except ValueError:
        raise Unauthorized(message="Invalid email or password")

    if scheme.lower() != "bearer":
        raise Unauthorized(message="Invalid email or password")

    try:
        payload = verify_access_token(
            token=token,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise Unauthorized(message="Invalid email or password")
        return int(user_id_str)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise Unauthorized(message="Invalid email or password")
