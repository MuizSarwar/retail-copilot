"""Test-only authorization routes.

These routes exist ONLY for testing authorization logic during development.
They are included in the test FastAPI app but NOT in the production app.
They will be removed when real domain endpoints are implemented in later parts.
"""

from fastapi import APIRouter, Depends

from app.modules.auth.dependencies.auth import require_admin, require_roles
from app.modules.auth.models.user import User

router = APIRouter()


@router.get("/test/admin-only", response_model=dict)
async def test_admin_only(
    current_user: User = Depends(require_admin()),
) -> dict:
    """Temporary admin-only test route. Removed in later parts."""
    return {
        "message": "Admin access granted",
        "user": current_user.email,
        "role": current_user.role.name,
    }


@router.get("/test/employee-or-admin", response_model=dict)
async def test_employee_or_admin(
    current_user: User = Depends(require_roles("admin", "employee")),
) -> dict:
    """Temporary route accessible to both admin and employee."""
    return {
        "message": "Authenticated access granted",
        "user": current_user.email,
        "role": current_user.role.name,
    }
