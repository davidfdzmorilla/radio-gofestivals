from fastapi import APIRouter

from app.api.v1.ws.nowplaying import router as nowplaying_router

ws_router = APIRouter()
ws_router.include_router(nowplaying_router)

__all__ = ["ws_router"]
