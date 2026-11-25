"""Seed script — idempotent database initialization.

Creates:
- Two roles: admin, employee
- One admin user, one employee user (credentials from .env)
- ~30 Bangladeshi grocery products across categories

Idempotent: running multiple times does not create duplicates or
overwrite existing user credentials.

Run with: uv run python scripts/seed.py
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# Ensure the project root is on sys.path so `app` is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.role import Role
from app.modules.auth.models.user import User
from app.modules.products.models.product import Product
from app.modules.sales.models.sale import Sale  # noqa: F401 — resolves forward reference in User.sales
from app.modules.sales.models.sale_item import SaleItem  # noqa: F401 — resolves forward reference in Sale.items


# Bangladeshi grocery products with realistic BDT prices.
# purchase_price = shop's cost, selling_price = customer price.
PRODUCTS = [
    # Rice
    {"name": "Basmati Rice (5kg)", "category": "Rice", "purchase_price": Decimal("550.00"), "selling_price": Decimal("600.00"), "available_quantity": 25, "min_stock_level": 5},
    {"name": "Basmati Rice (1kg)", "category": "Rice", "purchase_price": Decimal("115.00"), "selling_price": Decimal("130.00"), "available_quantity": 40, "min_stock_level": 10},
    {"name": "BR-28 Rice (5kg)", "category": "Rice", "purchase_price": Decimal("230.00"), "selling_price": Decimal("255.00"), "available_quantity": 30, "min_stock_level": 5},
    {"name": "BR-28 Rice (1kg)", "category": "Rice", "purchase_price": Decimal("48.00"), "selling_price": Decimal("55.00"), "available_quantity": 50, "min_stock_level": 10},

    # Lentils / Dal
    {"name": "Masur Dal (1kg)", "category": "Lentils", "purchase_price": Decimal("105.00"), "selling_price": Decimal("120.00"), "available_quantity": 35, "min_stock_level": 8},
    {"name": "Moong Dal (1kg)", "category": "Lentils", "purchase_price": Decimal("115.00"), "selling_price": Decimal("130.00"), "available_quantity": 30, "min_stock_level": 8},
    {"name": "Khesari Dal (1kg)", "category": "Lentils", "purchase_price": Decimal("65.00"), "selling_price": Decimal("75.00"), "available_quantity": 20, "min_stock_level": 5},

    # Oil
    {"name": "Soybean Oil (5L)", "category": "Oil", "purchase_price": Decimal("620.00"), "selling_price": Decimal("660.00"), "available_quantity": 15, "min_stock_level": 3},
    {"name": "Soybean Oil (1L)", "category": "Oil", "purchase_price": Decimal("130.00"), "selling_price": Decimal("145.00"), "available_quantity": 25, "min_stock_level": 5},
    {"name": "Mustard Oil (1L)", "category": "Oil", "purchase_price": Decimal("165.00"), "selling_price": Decimal("185.00"), "available_quantity": 12, "min_stock_level": 3},

    # Salt
    {"name": "Iodized Salt (1kg)", "category": "Salt", "purchase_price": Decimal("22.00"), "selling_price": Decimal("28.00"), "available_quantity": 60, "min_stock_level": 15},
    {"name": "Iodized Salt (500g)", "category": "Salt", "purchase_price": Decimal("12.00"), "selling_price": Decimal("15.00"), "available_quantity": 80, "min_stock_level": 20},

    # Sugar
    {"name": "Sugar (5kg)", "category": "Sugar", "purchase_price": Decimal("320.00"), "selling_price": Decimal("350.00"), "available_quantity": 20, "min_stock_level": 5},
    {"name": "Sugar (1kg)", "category": "Sugar", "purchase_price": Decimal("68.00"), "selling_price": Decimal("75.00"), "available_quantity": 45, "min_stock_level": 10},

    # Flour
    {"name": "Wheat Flour (Atta, 1kg)", "category": "Flour", "purchase_price": Decimal("42.00"), "selling_price": Decimal("48.00"), "available_quantity": 40, "min_stock_level": 10},
    {"name": "Maida (1kg)", "category": "Flour", "purchase_price": Decimal("38.00"), "selling_price": Decimal("44.00"), "available_quantity": 30, "min_stock_level": 8},
    {"name": "Suji (Semolina, 1kg)", "category": "Flour", "purchase_price": Decimal("45.00"), "selling_price": Decimal("52.00"), "available_quantity": 25, "min_stock_level": 8},

    # Spices
    {"name": "Turmeric Powder (100g)", "category": "Spices", "purchase_price": Decimal("35.00"), "selling_price": Decimal("42.00"), "available_quantity": 30, "min_stock_level": 10},
    {"name": "Cumin Powder (100g)", "category": "Spices", "purchase_price": Decimal("55.00"), "selling_price": Decimal("65.00"), "available_quantity": 20, "min_stock_level": 5},
    {"name": "Coriander Powder (100g)", "category": "Spices", "purchase_price": Decimal("45.00"), "selling_price": Decimal("52.00"), "available_quantity": 25, "min_stock_level": 5},
    {"name": "Red Chili Powder (100g)", "category": "Spices", "purchase_price": Decimal("60.00"), "selling_price": Decimal("70.00"), "available_quantity": 20, "min_stock_level": 5},
    {"name": "Garam Masala (50g)", "category": "Spices", "purchase_price": Decimal("45.00"), "selling_price": Decimal("55.00"), "available_quantity": 15, "min_stock_level": 5},
    {"name": "Salted Black Salt (100g)", "category": "Spices", "purchase_price": Decimal("25.00"), "selling_price": Decimal("30.00"), "available_quantity": 10, "min_stock_level": 3},

    # Tea
    {"name": "Tea Dust (250g)", "category": "Tea", "purchase_price": Decimal("110.00"), "selling_price": Decimal("125.00"), "available_quantity": 30, "min_stock_level": 8},
    {"name": "Tea Leaf (100g)", "category": "Tea", "purchase_price": Decimal("45.00"), "selling_price": Decimal("52.00"), "available_quantity": 40, "min_stock_level": 10},
    {"name": "Green Tea Bag (20pcs)", "category": "Tea", "purchase_price": Decimal("85.00"), "selling_price": Decimal("100.00"), "available_quantity": 15, "min_stock_level": 5},

    # Biscuits
    {"name": "Marie Biscuit (150g)", "category": "Biscuits", "purchase_price": Decimal("18.00"), "selling_price": Decimal("22.00"), "available_quantity": 60, "min_stock_level": 15},
    {"name": "Parle-G Biscuit (100g)", "category": "Biscuits", "purchase_price": Decimal("12.00"), "selling_price": Decimal("15.00"), "available_quantity": 70, "min_stock_level": 20},
    {"name": "Oreo Biscuit (60g)", "category": "Biscuits", "purchase_price": Decimal("28.00"), "selling_price": Decimal("35.00"), "available_quantity": 35, "min_stock_level": 10},

    # Low-stock items (below min_stock_level)
    {"name": "Premium Basmati Rice (1kg)", "category": "Rice", "purchase_price": Decimal("165.00"), "selling_price": Decimal("185.00"), "available_quantity": 2, "min_stock_level": 5},
    {"name": "Organic Mustard Oil (500ml)", "category": "Oil", "purchase_price": Decimal("95.00"), "selling_price": Decimal("110.00"), "available_quantity": 1, "min_stock_level": 3},
    {"name": "Saffron (1g)", "category": "Spices", "purchase_price": Decimal("280.00"), "selling_price": Decimal("350.00"), "available_quantity": 0, "min_stock_level": 1},
]


async def ensure_role(session: AsyncSession, name: str, description: str) -> Role:
    """Get or create a role. Idempotent."""
    result = await session.execute(select(Role).where(Role.name == name))
    role = result.scalar_one_or_none()
    if role is None:
        role = Role(name=name, description=description)
        session.add(role)
        await session.flush()
    return role


async def ensure_user(
    session: AsyncSession,
    email: str,
    password: str,
    role: Role,
) -> User:
    """Get or create a user. Idempotent — does not overwrite existing credentials."""
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(password),
            role_id=role.id,
            is_active=True,
        )
        session.add(user)
    return user


async def seed_products(session: AsyncSession) -> None:
    """Insert products if they don't already exist. Idempotent by name."""
    for product_data in PRODUCTS:
        result = await session.execute(
            select(Product).where(Product.name == product_data["name"])
        )
        if result.scalar_one_or_none() is None:
            product = Product(**product_data)
            session.add(product)


async def main() -> None:
    """Run the seed script."""
    print("Starting seed script...")

    admin_email = settings.seed_admin_email
    admin_password = settings.seed_admin_password
    employee_email = settings.seed_employee_email
    employee_password = settings.seed_employee_password

    if not admin_email or not admin_password:
        print("ERROR: SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD must be set in .env")
        return
    if not employee_email or not employee_password:
        print("ERROR: SEED_EMPLOYEE_EMAIL and SEED_EMPLOYEE_PASSWORD must be set in .env")
        return

    async with SessionLocal() as session:
        async with session.begin():
            # Create roles
            admin_role = await ensure_role(session, "admin", "Shop owner — full access")
            employee_role = await ensure_role(
                session, "employee", "Staff — read-only access"
            )

            # Create users (idempotent — won't overwrite existing credentials)
            await ensure_user(session, admin_email, admin_password, admin_role)
            await ensure_user(session, employee_email, employee_password, employee_role)

            # Create products
            await seed_products(session)

        await session.commit()

    print("Seed script completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
