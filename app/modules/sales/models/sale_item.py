"""SaleItem model.

Represents one line item within a sale. Links a sale to a product
with the quantity and price at the time of sale.
"""

from decimal import Decimal
from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Import Product and Sale to resolve string forward references in relationships.
from app.modules.products.models.product import Product  # noqa: F401
from app.modules.sales.models.sale import Sale  # noqa: F401


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_sale_items_unit_price_non_negative"),
        CheckConstraint("line_total >= 0", name="ck_sale_items_line_total_non_negative"),
    )

    # Relationships
    sale: Mapped["Sale"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="sale_items")

    def __repr__(self) -> str:
        return f"<SaleItem(id={self.id}, sale_id={self.sale_id}, product_id={self.product_id})>"
