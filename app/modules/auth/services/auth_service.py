"""Auth service — business logic for registration, login, and current user.

No HTTP concerns here. Database access goes through the repository layer.
Password hashing and JWT operations go through the security layer.
"""

from app.core.config import settings
from app.core.exceptions import Conflict, Forbidden, NotFound, Unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.repositories.user_repository import UserRepository


class AuthService:
    """Auth business logic."""

    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def register(self, email: str, password: str) -> dict:
        """Register a new employee account.

        Public registration ALWAYS creates an employee — never an admin.
        The client cannot select a role.
        """
        # Check for duplicate email
        if await self.repository.email_exists(email):
            raise Conflict(message="An account with this email already exists")

        # Resolve the employee role from the database
        employee_role = await self.repository.get_role_by_name("employee")
        if employee_role is None:
            # This should never happen if the seed script ran, but we handle
            # it safely instead of silently assigning an incorrect role.
            raise Forbidden(message="Employee role is not available")

        # Hash the password before storing
        password_hash = hash_password(password)

        # Create the user with the employee role
        user = await self.repository.create(
            email=email,
            password_hash=password_hash,
            role_id=employee_role.id,
        )

        return {
            "id": user.id,
            "email": user.email,
            "role": employee_role.name,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }

    async def login(self, email: str, password: str) -> dict:
        """Authenticate a user and return a JWT access token.

        Wrong email and wrong password return the SAME error so attackers
        cannot tell which one is incorrect.
        """
        user = await self.repository.get_by_email(email)

        # If user doesn't exist OR password is wrong, return the same 401
        # This prevents email enumeration attacks
        if user is None or not verify_password(password, user.password_hash):
            raise Unauthorized(message="Invalid email or password")

        if not user.is_active:
            raise Unauthorized(message="Invalid email or password")

        # Create JWT with user ID (sub) and expiry
        access_token = create_access_token(
            user_id=user.id,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            expire_minutes=settings.jwt_access_token_expire_minutes,
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    async def get_current_user(self, user_id: int) -> dict:
        """Get the current authenticated user with their role.

        The role is loaded from the database (not from JWT claims) so
        role changes take effect immediately.
        """
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise NotFound(message="User not found")

        # Load the role from the database
        role = await self.repository.get_role_by_name(user.role.name)
        role_name = role.name if role else "unknown"

        return {
            "id": user.id,
            "email": user.email,
            "role": role_name,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }
