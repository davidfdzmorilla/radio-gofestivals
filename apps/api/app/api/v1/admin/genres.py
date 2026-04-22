from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import AdminDep, RedisDep, SessionDep
from app.schemas.admin import GenreCreate, GenreOut, GenreUpdate
from app.services.admin import genres as admin_genres_service

router = APIRouter(prefix="/genres", tags=["admin-genres"])


@router.post(
    "",
    response_model=GenreOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_genre(
    body: GenreCreate,
    admin: AdminDep,  # noqa: ARG001
    session: SessionDep,
    redis: RedisDep,
) -> GenreOut:
    try:
        return await admin_genres_service.create_genre(session, redis, body)
    except admin_genres_service.GenreConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug_conflict",
        ) from exc


@router.put("/{genre_id}", response_model=GenreOut)
async def update_genre(
    genre_id: int,
    body: GenreUpdate,
    admin: AdminDep,  # noqa: ARG001
    session: SessionDep,
    redis: RedisDep,
) -> GenreOut:
    try:
        return await admin_genres_service.update_genre(session, redis, genre_id, body)
    except admin_genres_service.GenreNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="genre_not_found",
        ) from exc
    except admin_genres_service.GenreConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug_conflict",
        ) from exc


@router.delete("/{genre_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_genre(
    genre_id: int,
    admin: AdminDep,  # noqa: ARG001
    session: SessionDep,
    redis: RedisDep,
) -> Response:
    try:
        await admin_genres_service.delete_genre(session, redis, genre_id)
    except admin_genres_service.GenreInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="genre_in_use",
        ) from exc
    except admin_genres_service.GenreNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="genre_not_found",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
