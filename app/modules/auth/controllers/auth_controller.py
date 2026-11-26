"""Auth controller — HTTP layer for authentication endpoints.

Controllers only handle HTTP concerns: parse requests, call services,
return responses. No database queries, no password hashing, no JWT logic.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import AsyncSession, get_db
from app.modules.auth.dependencies.auth import get_current_user_id
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
)
from app.modules.auth.services.auth_service import AuthService

router = APIRouter()


def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    """Create an AuthService with a database session."""
    repository = UserRepository(session=db)
    return AuthService(repository=repository)


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    request: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Register a new employee account. Always creates an employee, never an admin."""
    result = await service.register(email=request.email, password=request.password)
    return UserResponse(**result)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """Authenticate and receive a JWT access token."""
    result = await service.login(email=request.email, password=request.password)
    return LoginResponse(**result)


@router.get("/me", response_model=UserResponse)
async def get_me(
    service: AuthService = Depends(get_auth_service),
    current_user_id: int = Depends(get_current_user_id),
) -> UserResponse:
    """Get the currently authenticated user with their role."""
    result = await service.get_current_user(user_id=current_user_id)
    return UserResponse(**result)
