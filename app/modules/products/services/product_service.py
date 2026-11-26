"""Product service — business logic for product CRUD.

No HTTP concerns here. Database access goes through the repository layer.
All business rules and validation decisions live in this layer.
"""

from decimal import Decimal
from typing import Optional

from app.core.exceptions import Conflict, NotFound
from app.modules.products.models.product import Product
from app.modules.products.repositories.product_repository import ProductRepository
from app.modules.products.schemas.products import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)


class ProductService:
    """Product business logic."""

    def __init__(self, repository: ProductRepository):
        self.repository = repository

    async def create_product(self, data: ProductCreate) -> ProductResponse:
        """Create a new product.

        Business rules:
        - Product name must be unique (case-insensitive, after trimming whitespace)
        - Raises Conflict if a product with the same name already exists
        """
        # Check for duplicate name (case-insensitive)
        existing = await self.repository.get_by_name(data.name)
        if existing is not None:
            raise Conflict(
                message=f"A product with the name '{data.name.strip()}' already exists"
            )

        product = await self.repository.create(
            name=data.name,
            category=data.category,
            purchase_price=data.purchase_price,
            selling_price=data.selling_price,
            available_quantity=data.available_quantity,
            min_stock_level=data.min_stock_level,
        )

        return ProductResponse.model_validate(product)

    async def get_products(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        low_stock: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ProductListResponse:
        """Get paginated products with optional search, category, and low-stock filters.

        Returns pagination metadata (total, page, page_size) alongside items.
        """
        products, total = await self.repository.get_all(
            search=search,
            category=category,
            low_stock=low_stock,
            page=page,
            page_size=page_size,
        )

        return ProductListResponse(
            items=[ProductResponse.model_validate(p) for p in products],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_product(self, product_id: int) -> ProductResponse:
        """Get a single product by ID.

        Raises NotFound if the product does not exist.
        """
        product = await self.repository.get_by_id(product_id)
        if product is None:
            raise NotFound(message=f"Product with ID {product_id} not found")

        return ProductResponse.model_validate(product)

    async def update_product(
        self, product_id: int, data: ProductUpdate
    ) -> ProductResponse:
        """Update an existing product.

        Business rules:
        - If the name is being changed, the new name must be unique
          (case-insensitive, after trimming whitespace)
        - Raises NotFound if the product does not exist
        - Raises Conflict if the new name duplicates an existing product
        """
        product = await self.repository.get_by_id(product_id)
        if product is None:
            raise NotFound(message=f"Product with ID {product_id} not found")

        # Check for duplicate name if name is being changed
        if data.name is not None:
            trimmed_name = data.name.strip()
            existing = await self.repository.get_by_name(trimmed_name)
            if existing is not None and existing.id != product_id:
                raise Conflict(
                    message=f"A product with the name '{trimmed_name}' already exists"
                )

        updated = await self.repository.update(
            product=product,
            name=data.name,
            category=data.category,
            purchase_price=data.purchase_price,
            selling_price=data.selling_price,
            available_quantity=data.available_quantity,
            min_stock_level=data.min_stock_level,
        )

        return ProductResponse.model_validate(updated)

    async def delete_product(self, product_id: int) -> None:
        """Delete a product.

        Business rules:
        - Products with sales history cannot be deleted (protects sales records)
        - Raises Conflict if the product has sale_items
        - Raises NotFound if the product does not exist
        """
        product = await self.repository.get_by_id(product_id)
        if product is None:
            raise NotFound(message=f"Product with ID {product_id} not found")

        # Check if the product has sales history
        if await self.repository.has_sales(product_id):
            raise Conflict(
                message=(
                    f"Cannot delete product '{product.name}': it has sales history. "
                    "Delete the related sales first."
                )
            )

        await self.repository.delete(product)

    async def get_categories(self) -> list[str]:
        """Get a list of distinct product categories."""
        return await self.repository.get_categories()
