from fastapi import APIRouter

from app.api.v1.users.auth import router as user_auth_router
from app.api.v1.users.favorites import router as favorites_router
from app.api.v1.users.password import router as password_router
from app.api.v1.users.votes import router as votes_router

users_router = APIRouter(tags=["users"])
users_router.include_router(user_auth_router)
users_router.include_router(password_router)
users_router.include_router(favorites_router)
users_router.include_router(votes_router)

__all__ = ["users_router"]
