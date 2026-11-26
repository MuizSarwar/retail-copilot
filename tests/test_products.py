"""Product CRUD tests (B4).

Tests cover products domain API:
- Full CRUD (create, list, get, update, delete)
- Search, filter, pagination
- Low-stock filtering
- Category listing
- Validation and error handling
- Role-based authorization

Uses the isolated retail_copilot_test database (APP_ENV=testing).
Never uses the development DATABASE_URL.
"""

import time
from decimal import Decimal
from datetime import datetime, timezone

import jwt
import pytest
from sqlalchemy import select
from httpx import ASGITransport, AsyncClient

from app.core.database import engine
from app.main import create_app
from tests.auth_test_routes import router as test_auth_router


def unique_email(base: str) -> str:
    """Generate a unique email address using a timestamp suffix."""
    return f"{base}.{int(time.time() * 1000)}@test.com"


async def create_user_via_repo(email: str, password: str, role_name: str):
    """Create a user directly via UserRepository (for test setup only)."""
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.modules.auth.repositories.user_repository import UserRepository

    async with SessionLocal() as session:
        repo = UserRepository(session=session)
        role = await repo.get_role_by_name(role_name)
        if role is None:
            raise RuntimeError(f"Role '{role_name}' not found in database")
        user = await repo.create(email, hash_password(password), role.id)
        await session.commit()
        await session.refresh(user)
        return user


async def login_and_get_token(app_client, email: str, password: str) -> str:
    """Helper to login and return the JWT access token."""
    login_resp = await app_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return login_resp.json()["access_token"]


@pytest.fixture
async def app_client():
    """Create a test client with the full FastAPI app.

    Includes test-only authorization routes.
    Disposes the database engine after each test.
    Cleans up products after each test to ensure test isolation.
    """
    from tests.auth_test_routes import router as test_auth_router

    app = create_app()
    app.include_router(test_auth_router, prefix="/api/v1/auth")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    # Clean up products and sale_items after each test to prevent data persistence across tests
    from app.core.database import SessionLocal
    from app.modules.products.models.product import Product
    from app.modules.sales.models.sale_item import SaleItem
    from sqlalchemy import delete
    async with SessionLocal() as session:
        await session.execute(delete(SaleItem))
        await session.execute(delete(Product))
        await session.commit()
    await engine.dispose()


async def seed_admin_and_employee(app_client):
    """Create an admin and an employee user, return their tokens."""
    admin_email = unique_email("admin")
    emp_email = unique_email("emp")

    await create_user_via_repo(admin_email, "AdminPass123!", "admin")
    await create_user_via_repo(emp_email, "EmpPass123!", "employee")

    admin_token = await login_and_get_token(app_client, admin_email, "AdminPass123!")
    emp_token = await login_and_get_token(app_client, emp_email, "EmpPass123!")

    return admin_token, emp_token


class TestProductCRUD:
    """POST /products, GET /products, GET /products/{id}, PUT /products/{id}, DELETE /products/{id}"""

    async def test_admin_creates_product(self, app_client):
        """Admin can create a new product → 201."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        response = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Basmati Rice",
                "category": "Rice",
                "purchase_price": "550.00",
                "selling_price": "600.00",
                "available_quantity": 25,
                "min_stock_level": 5,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Basmati Rice"
        assert data["category"] == "Rice"
        assert data["available_quantity"] == 25

    async def test_employee_cannot_create_product(self, app_client):
        """Employee cannot create a product → 403."""
        _, emp_token = await seed_admin_and_employee(app_client)

        response = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Test Product",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "forbidden"

    async def test_both_roles_can_list_products(self, app_client):
        """Both admin and employee can list products → 200."""
        admin_token, emp_token = await seed_admin_and_employee(app_client)

        # Create a product as admin
        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Test Rice",
                "category": "Rice",
                "purchase_price": "50.00",
                "selling_price": "60.00",
                "available_quantity": 10,
                "min_stock_level": 2,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Employee can list
        resp = await app_client.get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert resp.status_code == 200

        # Admin can list
        resp = await app_client.get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_both_roles_can_retrieve_product(self, app_client):
        """Both roles can retrieve a single product → 200."""
        admin_token, emp_token = await seed_admin_and_employee(app_client)

        create_resp = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Test Product",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        product_id = create_resp.json()["id"]

        # Employee can retrieve
        resp = await app_client.get(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert resp.status_code == 200

        # Admin can retrieve
        resp = await app_client.get(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_admin_updates_product(self, app_client):
        """Admin can update a product → 200."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        create_resp = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Original Name",
                "category": "Rice",
                "purchase_price": "50.00",
                "selling_price": "60.00",
                "available_quantity": 10,
                "min_stock_level": 2,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        product_id = create_resp.json()["id"]

        response = await app_client.put(
            f"/api/v1/products/{product_id}",
            json={
                "name": "Updated Name",
                "selling_price": "70.00",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["selling_price"] == "70.00"

    async def test_employee_cannot_update_product(self, app_client):
        """Employee cannot update a product → 403."""
        _, emp_token = await seed_admin_and_employee(app_client)

        create_resp = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Test Product",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        # Employee can't create, so use admin token to create first
        admin_token, _ = await seed_admin_and_employee(app_client)
        create_resp = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Test Product 2",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        product_id = create_resp.json()["id"]

        response = await app_client.put(
            f"/api/v1/products/{product_id}",
            json={"name": "Hacked Name"},
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert response.status_code == 403

    async def test_admin_deletes_product_without_sales(self, app_client):
        """Admin can delete a product without sales history → 204."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        create_resp = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Deletable Product",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        product_id = create_resp.json()["id"]

        response = await app_client.delete(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

        # Verify it's gone
        resp = await app_client.get(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_employee_cannot_delete_product(self, app_client):
        """Employee cannot delete a product → 403."""
        admin_token, emp_token = await seed_admin_and_employee(app_client)

        create_resp = await app_client.post(
            "/api/v1/products",
            json={
                "name": "To Delete",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        product_id = create_resp.json()["id"]

        response = await app_client.delete(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert response.status_code == 403


class TestProductSearchAndFilter:
    """GET /products with search, filter, pagination"""

    async def test_search_by_name(self, app_client):
        """Search by product name → 200."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Premium Basmati Rice",
                "category": "Rice",
                "purchase_price": "100.00",
                "selling_price": "120.00",
                "available_quantity": 10,
                "min_stock_level": 2,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Wheat Flour",
                "category": "Flour",
                "purchase_price": "40.00",
                "selling_price": "48.00",
                "available_quantity": 20,
                "min_stock_level": 5,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await app_client.get(
            "/api/v1/products?search=Basmati",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Premium Basmati Rice"

    async def test_case_insensitive_search(self, app_client):
        """Search is case-insensitive → 200."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Basmati Rice",
                "category": "Rice",
                "purchase_price": "100.00",
                "selling_price": "120.00",
                "available_quantity": 10,
                "min_stock_level": 2,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await app_client.get(
            "/api/v1/products?search=basmati",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    async def test_category_filter(self, app_client):
        """Filter by category → 200."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Basmati Rice",
                "category": "Rice",
                "purchase_price": "100.00",
                "selling_price": "120.00",
                "available_quantity": 10,
                "min_stock_level": 2,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Wheat Flour",
                "category": "Flour",
                "purchase_price": "40.00",
                "selling_price": "48.00",
                "available_quantity": 20,
                "min_stock_level": 5,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await app_client.get(
            "/api/v1/products?category=Rice",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["category"] == "Rice"

    async def test_low_stock_filter(self, app_client):
        """Filter by low stock → 200."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Low Stock Item",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 1,
                "min_stock_level": 5,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        await app_client.post(
            "/api/v1/products",
            json={
                "name": "High Stock Item",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 100,
                "min_stock_level": 5,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await app_client.get(
            "/api/v1/products?low_stock=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Low Stock Item"

    async def test_pagination_and_total(self, app_client):
        """Pagination returns total count → 200."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        for i in range(5):
            await app_client.post(
                "/api/v1/products",
                json={
                    "name": f"Product {i}",
                    "category": "Test",
                    "purchase_price": "10.00",
                    "selling_price": "15.00",
                    "available_quantity": i,
                    "min_stock_level": 1,
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        response = await app_client.get(
            "/api/v1/products?page=1&page_size=3",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 3
        assert len(data["items"]) == 3

    async def test_list_categories(self, app_client):
        """List available categories → 200."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Basmati Rice",
                "category": "Rice",
                "purchase_price": "100.00",
                "selling_price": "120.00",
                "available_quantity": 10,
                "min_stock_level": 2,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Wheat Flour",
                "category": "Flour",
                "purchase_price": "40.00",
                "selling_price": "48.00",
                "available_quantity": 20,
                "min_stock_level": 5,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await app_client.get(
            "/api/v1/products/categories",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "Rice" in data
        assert "Flour" in data


class TestProductValidation:
    """Validation and error handling"""

    async def test_negative_purchase_price_rejected(self, app_client):
        """Negative purchase price → 422."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        response = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Test",
                "category": "Test",
                "purchase_price": "-5.00",
                "selling_price": "10.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    async def test_negative_selling_price_rejected(self, app_client):
        """Negative selling price → 422."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        response = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Test",
                "category": "Test",
                "purchase_price": "5.00",
                "selling_price": "-10.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    async def test_negative_stock_quantity_rejected(self, app_client):
        """Negative stock quantity → 422."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        response = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Test",
                "category": "Test",
                "purchase_price": "5.00",
                "selling_price": "10.00",
                "available_quantity": -1,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    async def test_empty_product_name_rejected(self, app_client):
        """Empty product name → 422."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        response = await app_client.post(
            "/api/v1/products",
            json={
                "name": "",
                "category": "Test",
                "purchase_price": "5.00",
                "selling_price": "10.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    async def test_duplicate_product_name_returns_409(self, app_client):
        """Duplicate product name (case-insensitive) → 409."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Basmati Rice",
                "category": "Rice",
                "purchase_price": "100.00",
                "selling_price": "120.00",
                "available_quantity": 10,
                "min_stock_level": 2,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await app_client.post(
            "/api/v1/products",
            json={
                "name": "basmati rice",
                "category": "Rice",
                "purchase_price": "110.00",
                "selling_price": "130.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "conflict"

    async def test_missing_product_returns_404(self, app_client):
        """Missing product → 404."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        response = await app_client.get(
            "/api/v1/products/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "not_found"

    async def test_missing_authentication_returns_401(self, app_client):
        """Missing token → 401."""
        response = await app_client.get("/api/v1/products")
        assert response.status_code == 401

    async def test_invalid_authentication_returns_401(self, app_client):
        """Invalid token → 401."""
        response = await app_client.get(
            "/api/v1/products",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    async def test_low_stock_boundary(self, app_client):
        """Low stock boundary: available_quantity == min_stock_level is NOT low stock."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        # available_quantity == min_stock_level → NOT low stock
        await app_client.post(
            "/api/v1/products",
            json={
                "name": "Boundary Item",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 5,
                "min_stock_level": 5,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await app_client.get(
            "/api/v1/products?low_stock=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0  # Not low stock since qty == min_level

    async def test_product_with_sales_cannot_be_deleted(self, app_client):
        """Product with sales history → 409 Conflict.

        Creates a product via the API, then creates a sale and sale_item
        directly using SQLAlchemy models. Attempting to delete the product
        through the API returns 409. The product and sales records remain
        intact.
        """
        admin_token, _ = await seed_admin_and_employee(app_client)

        # Create product via API
        create_resp = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Product With Sales",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201
        product_id = create_resp.json()["id"]

        # Create a sale and sale_item directly via SQLAlchemy models
        from app.core.database import SessionLocal
        from app.modules.auth.models.user import User
        from app.modules.sales.models.sale import Sale
        from app.modules.sales.models.sale_item import SaleItem
        from decimal import Decimal
        from datetime import datetime, timezone

        async with SessionLocal() as session:
            # Find an existing user (created by seed_admin_and_employee)
            from app.modules.auth.repositories.user_repository import UserRepository
            repo = UserRepository(session=session)
            users_result = await session.execute(
                select(User).limit(1)
            )
            user = users_result.scalar_one()
            assert user is not None

            # Create sale
            sale = Sale(
                total_amount=Decimal("15.00"),
                sale_date=datetime.utcnow(),
                created_by=user.id,
                notes="Test sale for deletion protection",
            )
            session.add(sale)
            await session.flush()

            # Create sale_item referencing the product
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product_id,
                quantity=1,
                unit_price=Decimal("15.00"),
                line_total=Decimal("15.00"),
            )
            session.add(sale_item)
            await session.commit()

        # Attempt to delete product through API → should return 409
        response = await app_client.delete(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "conflict"
        assert "sales history" in data["error"]["message"].lower()

        # Verify the product still exists
        get_resp = await app_client.get(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == product_id

    async def test_product_without_sales_can_be_deleted(self, app_client):
        """Product without sales history → 204 No Content."""
        admin_token, _ = await seed_admin_and_employee(app_client)

        create_resp = await app_client.post(
            "/api/v1/products",
            json={
                "name": "Deletable Product",
                "category": "Test",
                "purchase_price": "10.00",
                "selling_price": "15.00",
                "available_quantity": 5,
                "min_stock_level": 1,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        product_id = create_resp.json()["id"]

        response = await app_client.delete(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

        # Verify it's gone
        get_resp = await app_client.get(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.status_code == 404
