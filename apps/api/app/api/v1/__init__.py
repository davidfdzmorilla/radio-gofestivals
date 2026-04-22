from fastapi import APIRouter

from app.api.v1.admin import admin_router
from app.api.v1.genres import router as genres_router
from app.api.v1.stations import router as stations_router
from app.api.v1.ws import ws_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(genres_router)
api_v1_router.include_router(stations_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(ws_router)

__all__ = ["api_v1_router"]
