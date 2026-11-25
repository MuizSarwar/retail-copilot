"""Ping service — B2 demonstration only.

Business logic layer. Depends on PingRepository (injected via Depends).
Real product business logic will be implemented in Part 9 (Products CRUD).
"""

from fastapi import Depends

from app.modules.products.repositories.ping_repository import PingRepository


class PingService:
    """Service that delegates to the repository layer."""

    def __init__(self, repository: PingRepository):
        self.repository = repository

    def ping(self) -> str:
        """Run business logic (currently just delegates to repository)."""
        repo_result = self.repository.ping()
        return f"PingService: business logic processed -> {repo_result}"


def get_ping_service(
    repository: PingRepository = Depends(PingRepository),
) -> PingService:
    """FastAPI dependency that constructs PingService with its repository."""
    return PingService(repository=repository)
