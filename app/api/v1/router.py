from fastapi import APIRouter

router = APIRouter()

# Module routers registered exactly once under /api/v1.
# Routes are defined inside module controllers, not duplicated here.
from app.modules.auth.controllers.router import router as auth_router
from app.modules.products.controllers.product_controller import router as products_router
from app.modules.sales.controllers.router import router as sales_router
from app.modules.stock_increase.controllers.router import router as stock_increase_router
from app.modules.dashboard.controllers.router import router as dashboard_router
from app.modules.chat.controllers.router import router as chat_router
from app.modules.documents.controllers.router import router as documents_router

router.include_router(auth_router, prefix="/auth")
router.include_router(products_router, prefix="/products")
router.include_router(sales_router, prefix="/sales")
router.include_router(stock_increase_router, prefix="/stock-increase")
router.include_router(dashboard_router, prefix="/dashboard")
router.include_router(chat_router, prefix="/chat")
router.include_router(documents_router, prefix="/documents")

# The /api/v1/health endpoint is defined directly in app/main.py.
