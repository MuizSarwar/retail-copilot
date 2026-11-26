"""User repository — database queries for users and roles.

All SQLAlchemy queries related to users and roles live here.
Controllers and services never contain raw database queries.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.role import Role
from app.modules.auth.models.user import User


class UserRepository:
    """Repository for user-related database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> Optional[User]:
        """Find a user by email address."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Find a user by ID, eagerly loading their role relationship."""
        result = await self.session.execute(
            select(User).where(User.id == user_id).options(selectinload(User.role))
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check if an email address is already registered."""
        user = await self.get_by_email(email)
        return user is not None

    async def create(
        self,
        email: str,
        password_hash: str,
        role_id: int,
    ) -> User:
        """Create a new user and return it."""
        user = User(
            email=email,
            password_hash=password_hash,
            role_id=role_id,
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_role_by_name(self, name: str) -> Optional[Role]:
        """Find a role by name (e.g. 'employee' or 'admin')."""
        result = await self.session.execute(
            select(Role).where(Role.name == name)
        )
        return result.scalar_one_or_none()
