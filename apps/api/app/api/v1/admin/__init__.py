from fastapi import APIRouter

from app.api.v1.admin.auth import router as auth_router
from app.api.v1.admin.genres import router as admin_genres_router
from app.api.v1.admin.operations import router as admin_operations_router
from app.api.v1.admin.stations import router as admin_stations_router

admin_router = APIRouter(prefix="/admin", tags=["admin"])
admin_router.include_router(auth_router)
admin_router.include_router(admin_stations_router)
admin_router.include_router(admin_genres_router)
admin_router.include_router(admin_operations_router)

__all__ = ["admin_router"]
