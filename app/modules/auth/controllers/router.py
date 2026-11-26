"""Auth controller router.

Defines /register, /login, /me routes under the /auth prefix.
"""

from fastapi import APIRouter

from app.modules.auth.controllers.auth_controller import router as auth_router

router = APIRouter()
router.include_router(auth_router)
