"""Product model.

Represents an inventory item in the shop. Full CRUD is supported.
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, Index, func, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, created_at_column, updated_at_column


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    available_quantity: Mapped[int] = mapped_column(default=0, nullable=False)
    min_stock_level: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    __table_args__ = (
        CheckConstraint("available_quantity >= 0", name="ck_products_available_quantity_non_negative"),
    )

    # Relationship: one product has many sale items
    sale_items: Mapped[list["SaleItem"]] = relationship(back_populates="product")

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name={self.name})>"


# Functional unique index on lower(trim(name)) — matches Alembic migration
# a1b2c3d4e5f6. Same index name and expression.
Index("idx_products_name_lower", func.lower(func.trim(Product.name)), unique=True)
