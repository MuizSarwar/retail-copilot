"""Product controller — HTTP layer for product endpoints.

Controllers only handle HTTP concerns: parse requests, call services,
return responses. No database queries, no business logic.

Route ordering matters: /products/categories is defined BEFORE
/products/{product_id} to prevent FastAPI from matching "categories"
as a product_id.
"""

from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status

from app.core.database import AsyncSession, get_db
from app.modules.auth.dependencies.auth import get_current_user, require_admin
from app.modules.auth.models.user import User
from app.modules.products.repositories.product_repository import ProductRepository
from app.modules.products.schemas.products import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.modules.products.services.product_service import ProductService

router = APIRouter()


def get_product_repository(db: AsyncSession = Depends(get_db)) -> ProductRepository:
    """Create a ProductRepository with an active database session."""
    return ProductRepository(session=db)


def get_product_service(
    repository: ProductRepository = Depends(get_product_repository),
) -> ProductService:
    """Create a ProductService with the given repository."""
    return ProductService(repository=repository)


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["products"],
)
async def create_product(
    data: ProductCreate,
    service: ProductService = Depends(get_product_service),
    _admin: User = Depends(require_admin()),
) -> ProductResponse:
    """Create a new product. Admin-only."""
    return await service.create_product(data)


@router.get(
    "",
    response_model=ProductListResponse,
    tags=["products"],
)
async def list_products(
    search: Optional[str] = Query(
        None, description="Case-insensitive substring search on product name"
    ),
    category: Optional[str] = Query(None, description="Filter by product category"),
    low_stock: Optional[bool] = Query(
        None, description="If true, only show products below minimum stock level"
    ),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    service: ProductService = Depends(get_product_service),
    _user: User = Depends(get_current_user),
) -> ProductListResponse:
    """List products with optional search, category, and low-stock filters.
    Accessible to both employees and admins."""
    return await service.get_products(
        search=search,
        category=category,
        low_stock=low_stock,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/categories",
    response_model=list[str],
    tags=["products"],
)
async def list_categories(
    service: ProductService = Depends(get_product_service),
    _user: User = Depends(get_current_user),
) -> list[str]:
    """List all distinct product categories.
    Accessible to both employees and admins.
    """
    return await service.get_categories()


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    tags=["products"],
)
async def get_product(
    product_id: int,
    service: ProductService = Depends(get_product_service),
    _user: User = Depends(get_current_user),
) -> ProductResponse:
    """Get a single product by ID.
    Accessible to both employees and admins."""
    return await service.get_product(product_id)


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    tags=["products"],
)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    service: ProductService = Depends(get_product_service),
    _admin: User = Depends(require_admin()),
) -> ProductResponse:
    """Update an existing product. Admin-only."""
    return await service.update_product(product_id, data)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["products"],
)
async def delete_product(
    product_id: int,
    service: ProductService = Depends(get_product_service),
    _admin: User = Depends(require_admin()),
) -> None:
    """Delete a product. Admin-only.
    Products with sales history cannot be deleted."""
    await service.delete_product(product_id)
