"""Authentication dependencies — JWT verification and user extraction.

Dependencies used by controllers to authenticate requests and extract
the current user's ID and role from a Bearer JWT, loading them from
PostgreSQL on every request (never trusting JWT claims for role info).
"""

from typing import Callable, Optional

from fastapi import Depends, Header
import jwt

from app.core.config import settings
from app.core.database import AsyncSession, get_db
from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import verify_access_token
from app.modules.auth.models.role import Role
from app.modules.auth.models.user import User
from app.modules.auth.repositories.user_repository import UserRepository


async def get_user_repository(
    db=Depends(get_db),
) -> UserRepository:
    """Create a UserRepository with an active database session."""
    return UserRepository(session=db)


async def get_current_user(
    repository: UserRepository = Depends(get_user_repository),
    authorization: Optional[str] = Header(None),
) -> User:
    """Validate JWT, extract user_id, and fetch user + role from PostgreSQL.

    Returns the User SQLAlchemy model with its role eagerly loaded.
    Raises Unauthorized if the token is missing, invalid, expired, or
    the user is inactive.
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
        user_id = int(user_id_str)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise Unauthorized(message="Invalid email or password")

    # Fetch user from PostgreSQL (role is eagerly loaded via selectinload)
    user = await repository.get_by_id(user_id)
    if user is None:
        raise Unauthorized(message="Invalid email or password")

    if not user.is_active:
        raise Unauthorized(message="Invalid email or password")

    return user


def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory that returns a dependency checking the user's role.

    Usage:
        @router.post("/products", dependencies=[Depends(require_roles("admin"))])

    Raises Forbidden (403) if the user's role is not in allowed_roles.
    """
    async def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role.name not in allowed_roles:
            raise Forbidden(message="Insufficient permissions")
        return current_user

    return role_dependency


def require_admin() -> Callable:
    """Dependency that requires the admin role."""
    return require_roles("admin")
