"""Ping repository — B2 demonstration only.

This is a temporary placeholder. It does NOT connect to a real database.
Real product repository queries will be implemented in Part 4 (database models)
and Part 9 (Products CRUD).
"""


class PingRepository:
    """Repository that returns a static ping response (no database)."""

    def ping(self) -> str:
        """Return a static message to demonstrate the repository layer."""
        return "PingRepository: repository layer responded (no DB yet)"
