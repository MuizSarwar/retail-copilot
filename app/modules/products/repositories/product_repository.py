"""Product repository — database queries for products.

All SQLAlchemy queries related to products live here.
Controllers and services never contain raw database queries.
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.models.product import Product


class ProductRepository:
    """Repository for product-related database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        """Find a product by its primary key.

        Eagerly loads sale_items so the service can check whether
        the product has sales history before allowing deletion.
        """
        result = await self.session.execute(
            select(Product).where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Product]:
        """Find a product by name, case-insensitively.

        Used for duplicate-name detection. Trims surrounding whitespace
        from the input before comparing.
        """
        trimmed = name.strip()
        result = await self.session.execute(
            select(Product).where(func.lower(Product.name) == func.lower(trimmed))
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        low_stock: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Product], int]:
        """Get paginated products with optional search, category, and low-stock filters.

        Returns a tuple of (products, total_count) so the service can
        build pagination metadata.

        Filters:
        - search: case-insensitive substring match on product name
        - category: exact match on product category
        - low_stock: if True, only products where available_quantity < min_stock_level
        """
        query = select(Product)

        # Apply search filter (case-insensitive substring match on name)
        if search:
            query = query.where(Product.name.ilike(f"%{search.strip()}%"))

        # Apply category filter (exact match)
        if category:
            query = query.where(Product.category == category)

        # Apply low-stock filter
        if low_stock:
            query = query.where(Product.available_quantity < Product.min_stock_level)

        # Count total matching records before pagination
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.session.execute(query)
        products = result.scalars().all()

        return products, total

    async def create(
        self,
        name: str,
        category: str,
        purchase_price,
        selling_price,
        available_quantity: int,
        min_stock_level: int,
    ) -> Product:
        """Insert a new product and return it."""
        product = Product(
            name=name.strip(),
            category=category.strip(),
            purchase_price=purchase_price,
            selling_price=selling_price,
            available_quantity=available_quantity,
            min_stock_level=min_stock_level,
        )
        self.session.add(product)
        await self.session.flush()
        return product

    async def update(
        self,
        product: Product,
        name: Optional[str] = None,
        category: Optional[str] = None,
        purchase_price=None,
        selling_price=None,
        available_quantity: Optional[int] = None,
        min_stock_level: Optional[int] = None,
    ) -> Product:
        """Update product fields. Only provided fields are changed."""
        if name is not None:
            product.name = name.strip()
        if category is not None:
            product.category = category.strip()
        if purchase_price is not None:
            product.purchase_price = purchase_price
        if selling_price is not None:
            product.selling_price = selling_price
        if available_quantity is not None:
            product.available_quantity = available_quantity
        if min_stock_level is not None:
            product.min_stock_level = min_stock_level

        await self.session.flush()
        await self.session.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        """Delete a product from the database."""
        await self.session.delete(product)
        await self.session.flush()

    async def get_categories(self) -> list[str]:
        """Get a list of distinct product categories."""
        result = await self.session.execute(
            select(Product.category).distinct().order_by(Product.category)
        )
        return [row[0] for row in result.all()]

    async def has_sales(self, product_id: int) -> bool:
        """Check if a product has any sale items (sales history).

        Queries the sale_items table through the product relationship.
        """
        from app.modules.sales.models.sale_item import SaleItem

        result = await self.session.execute(
            select(SaleItem.id).where(SaleItem.product_id == product_id).limit(1)
        )
        return result.scalar_one_or_none() is not None
