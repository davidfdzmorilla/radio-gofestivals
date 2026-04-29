from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminDep, SessionDep
from app.core.logging import get_logger
from app.repos import admin_jobs as jobs_repo
from app.schemas.admin_jobs import (
    CatalogEntry,
    JobCreateRequest,
    JobListPage,
    JobOut,
)
from app.services.admin import operations as ops_service
from app.services.admin.operations import (
    CommandNotAllowedError,
    InvalidParamsError,
)
from app.services.admin.operations_catalog import ALLOWED_COMMANDS

router = APIRouter(prefix="/operations", tags=["admin-operations"])
log = get_logger("app.admin.operations")


@router.get("/catalog", response_model=list[CatalogEntry])
async def get_catalog(
    admin: AdminDep,  # noqa: ARG001
) -> list[CatalogEntry]:
    return [
        CatalogEntry(
            command=key,
            label=spec["label"],
            description=spec["description"],
            timeout=int(spec["timeout"]),
            params_schema=spec["params_model"].model_json_schema(),
        )
        for key, spec in ALLOWED_COMMANDS.items()
    ]


@router.post(
    "/run",
    response_model=JobOut,
    status_code=status.HTTP_201_CREATED,
)
async def run_command(
    body: JobCreateRequest,
    admin: AdminDep,
    session: SessionDep,
) -> JobOut:
    try:
        job = await ops_service.enqueue_job(
            session,
            admin_id=admin.id,
            command=body.command,
            raw_params=body.params,
        )
    except CommandNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"command_not_allowed: {exc}",
        ) from exc
    except InvalidParamsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid_params: {exc}",
        ) from exc

    log.info(
        "admin_job_enqueued",
        admin_id=str(admin.id),
        command=body.command,
        job_id=job["id"],
    )
    job["admin_email"] = admin.email
    return JobOut(**job)


@router.get("/jobs", response_model=JobListPage)
async def list_jobs(
    admin: AdminDep,  # noqa: ARG001
    session: SessionDep,
    status_filter: Annotated[
        Literal["pending", "running", "success", "failed", "timeout"]
        | None,
        Query(alias="status"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JobListPage:
    items, total, pages = await jobs_repo.list_jobs(
        session, page=page, size=size, status=status_filter,
    )
    return JobListPage(
        items=[JobOut(**item) for item in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: int,
    admin: AdminDep,  # noqa: ARG001
    session: SessionDep,
) -> JobOut:
    job = await jobs_repo.get_job(session, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found",
        )
    return JobOut(**job)
