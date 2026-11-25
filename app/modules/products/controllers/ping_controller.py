"""Ping controller — B2 demonstration only.

HTTP layer only: defines the route, calls the service, returns a response.
No SQL, no LLM calls. Real product routes will be implemented in Part 9.

TEMPORARY: The GET /api/v1/products/ping endpoint is B2 demonstration code.
It will be replaced when real product functionality is implemented.
"""

from fastapi import APIRouter, Depends

from app.modules.products.services.ping_service import PingService, get_ping_service

router = APIRouter()


@router.get("/ping", tags=["products", "b2-demo"])
async def ping(service: PingService = Depends(get_ping_service)) -> dict:
    """Temporary B2 demonstration endpoint.

    Flow: Client -> Controller -> Service -> Repository -> Service -> Controller -> Client
    """
    result = service.ping()
    return {"message": result, "demo": "B2 modular structure"}
