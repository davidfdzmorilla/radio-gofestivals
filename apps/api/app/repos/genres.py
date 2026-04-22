from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class GenreRow(NamedTuple):
    id: int
    slug: str
    name: str
    color_hex: str
    parent_id: int | None
    sort_order: int
    station_count: int


async def fetch_genres_with_counts(session: AsyncSession) -> list[GenreRow]:
    stmt = text(
        """
        SELECT
            g.id,
            g.slug,
            g.name,
            g.color_hex,
            g.parent_id,
            g.sort_order,
            COALESCE(SUM(CASE WHEN s.status = 'active' THEN 1 ELSE 0 END), 0)::int AS station_count
        FROM genres g
        LEFT JOIN station_genres sg ON sg.genre_id = g.id
        LEFT JOIN stations s ON s.id = sg.station_id
        GROUP BY g.id
        ORDER BY g.sort_order ASC, g.name ASC
        """
    )
    result = await session.execute(stmt)
    return [GenreRow(*row) for row in result.all()]
