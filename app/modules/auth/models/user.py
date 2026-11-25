"""User model.

Represents a shop user (admin or employee). Password is hashed with Argon2.
Role is loaded from the roles table at login time (not hardcoded in JWT).
"""

from datetime import datetime
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, created_at_column, updated_at_column


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    # Relationship: many users belong to one role
    role: Mapped["Role"] = relationship(back_populates="users")

    # Relationship: one user has many sales
    sales: Mapped[list["Sale"]] = relationship(back_populates="creator")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
