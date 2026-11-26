"""Pydantic schemas for products.

These schemas define request and response bodies for product endpoints.
Password hashes are never relevant here - products have no secrets.
"""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class ProductCreate(BaseModel):
    """Request schema for creating a new product."""

    name: str = Field(..., min_length=1, max_length=200, description="Product name")
    category: str = Field(..., min_length=1, max_length=100, description="Product category")
    purchase_price: Decimal = Field(..., ge=0, description="Cost price (must be >= 0)")
    selling_price: Decimal = Field(..., ge=0, description="Selling price (must be >= 0)")
    available_quantity: int = Field(..., ge=0, description="Current stock quantity (>= 0)")
    min_stock_level: int = Field(..., ge=0, description="Low-stock threshold (>= 0)")


class ProductUpdate(BaseModel):
    """Request schema for updating an existing product.

    All fields are optional - only provided fields are updated.
    """

    name: str | None = Field(None, min_length=1, max_length=200)
    category: str | None = Field(None, min_length=1, max_length=100)
    purchase_price: Decimal | None = Field(None, ge=0)
    selling_price: Decimal | None = Field(None, ge=0)
    available_quantity: int | None = Field(None, ge=0)
    min_stock_level: int | None = Field(None, ge=0)


class ProductResponse(BaseModel):
    """Response schema for product data - never exposes internal DB fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    purchase_price: Decimal
    selling_price: Decimal
    available_quantity: int
    min_stock_level: int
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """Paginated product list response with metadata."""

    items: list[ProductResponse]
    total: int
    page: int
    page_size: int


class CategoryResponse(BaseModel):
    """Response schema for a product category."""

    name: str


class CategoriesListResponse(BaseModel):
    """Response schema for list of product categories."""

    categories: list[CategoryResponse]
