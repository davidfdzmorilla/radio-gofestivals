from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminDep, SessionDep
from app.schemas.admin_dashboard import DashboardStats
from app.services.admin.dashboard_stats import get_dashboard_stats

router = APIRouter(prefix="/dashboard", tags=["admin-dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    admin: AdminDep,  # noqa: ARG001 — enforces auth
    session: SessionDep,
) -> DashboardStats:
    return await get_dashboard_stats(session)
