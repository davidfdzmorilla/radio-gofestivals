from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.schemas.admin import GenreCreate, GenreOut, GenreUpdate
from app.services.genres import invalidate_genres_cache

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession


class GenreConflictError(Exception):
    pass


class GenreNotFoundError(Exception):
    pass


class GenreInUseError(Exception):
    pass


def _row_to_out(row: tuple[Any, ...]) -> GenreOut:
    return GenreOut(
        id=int(row[0]),
        slug=str(row[1]),
        name=str(row[2]),
        parent_id=row[3],
        color_hex=str(row[4]),
        sort_order=int(row[5]),
        description=row[6],
    )


async def create_genre(
    session: AsyncSession,
    redis: Redis[str],
    data: GenreCreate,
) -> GenreOut:
    try:
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO genres (slug, name, parent_id, color_hex, sort_order, description)
                    VALUES (:slug, :name, :parent_id, :color_hex, :sort_order, :description)
                    RETURNING id, slug, name, parent_id, color_hex, sort_order, description
                    """,
                ),
                data.model_dump(),
            )
        ).first()
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        msg = f"slug '{data.slug}' already exists"
        raise GenreConflictError(msg) from exc

    if row is None:
        msg = "insert returned no row"
        raise RuntimeError(msg)

    await invalidate_genres_cache(redis)
    return _row_to_out(tuple(row))


async def update_genre(
    session: AsyncSession,
    redis: Redis[str],
    genre_id: int,
    data: GenreUpdate,
) -> GenreOut:
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if not updates:
        row = (
            await session.execute(
                text(
                    "SELECT id, slug, name, parent_id, color_hex, sort_order, description "
                    "FROM genres WHERE id = :id",
                ),
                {"id": genre_id},
            )
        ).first()
        if row is None:
            raise GenreNotFoundError
        return _row_to_out(tuple(row))

    set_fragments = ", ".join(f"{col} = :{col}" for col in updates)
    params = {**updates, "id": genre_id}
    try:
        row = (
            await session.execute(
                text(
                    f"""
                    UPDATE genres SET {set_fragments}
                    WHERE id = :id
                    RETURNING id, slug, name, parent_id, color_hex, sort_order, description
                    """,  # noqa: S608
                ),
                params,
            )
        ).first()
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        msg = "slug conflict"
        raise GenreConflictError(msg) from exc

    if row is None:
        raise GenreNotFoundError

    await invalidate_genres_cache(redis)
    return _row_to_out(tuple(row))


async def delete_genre(
    session: AsyncSession,
    redis: Redis[str],
    genre_id: int,
) -> None:
    in_use = (
        await session.execute(
            text("SELECT COUNT(*) FROM station_genres WHERE genre_id = :id"),
            {"id": genre_id},
        )
    ).scalar_one()
    if int(in_use) > 0:
        raise GenreInUseError

    result = await session.execute(
        text("DELETE FROM genres WHERE id = :id RETURNING id"),
        {"id": genre_id},
    )
    if result.first() is None:
        raise GenreNotFoundError
    await session.commit()
    await invalidate_genres_cache(redis)
