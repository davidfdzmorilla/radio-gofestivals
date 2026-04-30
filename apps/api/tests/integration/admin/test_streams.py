from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

from tests.integration.admin.test_stations_list import _seed_station

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _add_stream(
    db: AsyncSession,
    *,
    station_id: uuid.UUID,
    url: str,
    is_primary: bool = False,
    bitrate: int | None = 128,
) -> uuid.UUID:
    sid = (
        await db.execute(
            text(
                """
                INSERT INTO station_streams
                    (station_id, stream_url, codec, bitrate,
                     is_primary, status)
                VALUES (:sid, :url, 'mp3', :br, :primary,
                        CAST('active' AS stream_status))
                RETURNING id
                """,
            ),
            {
                "sid": str(station_id),
                "url": url,
                "br": bitrate,
                "primary": is_primary,
            },
        )
    ).scalar_one()
    await db.commit()
    return uuid.UUID(str(sid))


async def test_401_without_auth(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="auth-1")
    stream_id = await _add_stream(
        db_session,
        station_id=sid,
        url="https://x/secondary.mp3",
        is_primary=False,
    )
    resp = await client.patch(
        f"/api/v1/admin/streams/{stream_id}/promote-primary",
    )
    assert resp.status_code == 401


async def test_404_for_missing_stream(logged_in_client: AsyncClient) -> None:
    fake = "00000000-0000-0000-0000-000000000000"
    resp = await logged_in_client.patch(
        f"/api/v1/admin/streams/{fake}/promote-primary",
    )
    assert resp.status_code == 404


async def test_400_when_already_primary(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(
        db_session, slug="alr-1", primary_stream_url=None,
    )
    primary = await _add_stream(
        db_session, station_id=sid, url="https://x/p.mp3", is_primary=True,
    )
    resp = await logged_in_client.patch(
        f"/api/v1/admin/streams/{primary}/promote-primary",
    )
    assert resp.status_code == 400
    assert "already_primary" in resp.json()["detail"]


async def test_promote_swaps_primary_and_audits(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(
        db_session, slug="prom-1", primary_stream_url=None,
    )
    old_primary = await _add_stream(
        db_session, station_id=sid, url="https://x/a.mp3",
        is_primary=True, bitrate=64,
    )
    target = await _add_stream(
        db_session, station_id=sid, url="https://x/b.mp3",
        is_primary=False, bitrate=192,
    )

    resp = await logged_in_client.patch(
        f"/api/v1/admin/streams/{target}/promote-primary",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["promoted_stream_id"] == str(target)
    assert body["demoted_stream_id"] == str(old_primary)
    assert body["station_id"] == str(sid)

    rows = (
        await db_session.execute(
            text(
                "SELECT id::text, is_primary FROM station_streams "
                "WHERE station_id = :sid",
            ),
            {"sid": str(sid)},
        )
    ).all()
    flags = {r[0]: bool(r[1]) for r in rows}
    assert flags[str(target)] is True
    assert flags[str(old_primary)] is False

    audit = (
        await db_session.execute(
            text(
                "SELECT decision::text, notes FROM curation_log "
                "WHERE station_id = :sid ORDER BY id DESC LIMIT 1",
            ),
            {"sid": str(sid)},
        )
    ).first()
    assert audit is not None
    assert audit[0] == "change_primary_stream"
    assert "Promoted" in audit[1]


async def test_promote_when_no_previous_primary(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(
        db_session, slug="np-1", primary_stream_url=None,
    )
    target = await _add_stream(
        db_session, station_id=sid, url="https://x/only.mp3",
        is_primary=False,
    )
    resp = await logged_in_client.patch(
        f"/api/v1/admin/streams/{target}/promote-primary",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["demoted_stream_id"] is None
    assert body["promoted_stream_id"] == str(target)
