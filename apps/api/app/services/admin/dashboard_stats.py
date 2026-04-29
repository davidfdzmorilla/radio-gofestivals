from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.schemas.admin_dashboard import (
    ActivityEntry,
    CountryCount,
    DashboardKpis,
    DashboardStats,
    GenreCount,
    QualityBucket,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_dashboard_stats(session: AsyncSession) -> DashboardStats:
    """Build the full dashboard payload from a handful of aggregate queries.

    All metrics are computed against the live `stations` table and the
    `curation_log` audit table — no caching, the dashboard is a manual
    snapshot the operator refreshes.
    """
    kpi_row = (
        await session.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'active') AS active,
                    COUNT(*) FILTER (WHERE status = 'active' AND curated = true) AS curated,
                    COUNT(*) FILTER (WHERE status = 'broken') AS broken,
                    COALESCE(
                        AVG(quality_score) FILTER (WHERE status = 'active'),
                        0
                    ) AS avg_quality
                FROM stations
                """,
            ),
        )
    ).first()
    kpis = DashboardKpis(
        stations_active=int(kpi_row[0] or 0) if kpi_row else 0,
        stations_curated=int(kpi_row[1] or 0) if kpi_row else 0,
        stations_broken=int(kpi_row[2] or 0) if kpi_row else 0,
        avg_quality_active=(
            round(float(kpi_row[3] or 0), 1) if kpi_row else 0.0
        ),
    )

    quality_rows = (
        await session.execute(
            text(
                """
                SELECT
                    CASE
                        WHEN quality_score < 30 THEN '0-29'
                        WHEN quality_score < 50 THEN '30-49'
                        WHEN quality_score < 70 THEN '50-69'
                        WHEN quality_score < 90 THEN '70-89'
                        ELSE '90+'
                    END AS bucket,
                    COUNT(*) AS n,
                    MIN(quality_score) AS min_score
                FROM stations
                WHERE status = 'active'
                GROUP BY bucket
                ORDER BY MIN(quality_score)
                """,
            ),
        )
    ).all()
    quality_distribution = [
        QualityBucket(bucket=str(r[0]), count=int(r[1])) for r in quality_rows
    ]

    genre_rows = (
        await session.execute(
            text(
                """
                SELECT g.name, COUNT(DISTINCT sg.station_id) AS n
                FROM genres g
                JOIN station_genres sg ON g.id = sg.genre_id
                JOIN stations s ON sg.station_id = s.id
                WHERE s.status = 'active' AND s.curated = true
                GROUP BY g.name
                ORDER BY n DESC, g.name ASC
                LIMIT 10
                """,
            ),
        )
    ).all()
    top_genres = [
        GenreCount(name=str(r[0]), count=int(r[1])) for r in genre_rows
    ]

    country_rows = (
        await session.execute(
            text(
                """
                SELECT country_code, COUNT(*) AS n
                FROM stations
                WHERE status = 'active' AND country_code IS NOT NULL
                GROUP BY country_code
                ORDER BY n DESC, country_code ASC
                LIMIT 10
                """,
            ),
        )
    ).all()
    top_countries = [
        CountryCount(country_code=str(r[0]), count=int(r[1]))
        for r in country_rows
    ]

    activity_rows = (
        await session.execute(
            text(
                """
                SELECT
                    cl.id,
                    cl.decision::text AS decision,
                    cl.station_id,
                    s.name AS station_name,
                    s.slug AS station_slug,
                    a.email AS admin_email,
                    cl.notes,
                    cl.created_at
                FROM curation_log cl
                LEFT JOIN stations s ON cl.station_id = s.id
                LEFT JOIN admins a ON cl.admin_id = a.id
                ORDER BY cl.created_at DESC, cl.id DESC
                LIMIT 20
                """,
            ),
        )
    ).all()
    recent_activity = [
        ActivityEntry(
            id=int(r[0]),
            decision=str(r[1]),
            station_id=uuid.UUID(str(r[2])),
            station_name=r[3],
            station_slug=r[4],
            admin_email=r[5],
            notes=r[6],
            created_at=r[7],
        )
        for r in activity_rows
    ]

    return DashboardStats(
        kpis=kpis,
        quality_distribution=quality_distribution,
        top_genres_curated=top_genres,
        top_countries=top_countries,
        recent_activity=recent_activity,
    )
