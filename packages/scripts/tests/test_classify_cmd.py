from __future__ import annotations

from typing import TYPE_CHECKING, Any

import respx
from sqlalchemy import text

from scripts.classify_cmd import backfill_tags, export_rows, run_classification
from scripts.rb_client import RadioBrowserClient
from scripts.rb_sync import run_sync

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

U1 = "00000000-0000-0000-0000-0000000000a1"
U2 = "00000000-0000-0000-0000-0000000000a2"
U3 = "00000000-0000-0000-0000-0000000000a3"


def _item(uuid: str, name: str, tags: str) -> dict[str, Any]:
    return {
        "stationuuid": uuid,
        "name": name,
        "url": f"https://stream.example.com/{uuid[-2:]}.mp3",
        "url_resolved": f"https://stream.example.com/{uuid[-2:]}.mp3",
        "countrycode": "de",
        "codec": "mp3",
        "bitrate": 128,
        "tags": tags,
    }


async def _insert(db: AsyncSession, uuid: str, slug: str, *, tags: list[str] | None = None) -> None:
    await db.execute(
        text(
            "INSERT INTO stations (rb_uuid, slug, name, status, source, rb_tags) "
            "VALUES (CAST(:u AS uuid), :s, :s, 'active', 'radio-browser', "
            ":t)",
        ),
        {"u": uuid, "s": slug, "t": tags},
    )
    await db.commit()


@respx.mock
async def test_rb_sync_stores_normalized_tags_on_insert_and_update(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(
        json=[_item(U1, "Radio One", " Techno, techno ,Électro")],
    )
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=10, client=client)
    tags = (await db_session.execute(text("SELECT rb_tags FROM stations"))).scalar_one()
    assert tags == ["techno", "electro"]

    respx.clear()
    respx.get(url__regex=r"https://host-a\.example/.*").respond(
        json=[_item(U1, "Radio One", "techno,house")],
    )
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=10, client=client)
    db_session.expire_all()
    tags = (await db_session.execute(text("SELECT rb_tags FROM stations"))).scalar_one()
    assert tags == ["techno", "house"]


@respx.mock
async def test_backfill_fills_only_null_tags_and_dry_run_writes_nothing(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _insert(db_session, U1, "needs-tags")
    await _insert(db_session, U2, "already", tags=["house"])
    route = respx.get(url__regex=r"https://host-a\.example/json/stations/byuuid.*").respond(
        json=[_item(U1, "needs-tags", "Techno,Rock")],
    )
    client = RadioBrowserClient(servers=["host-a.example"])

    stats = await backfill_tags(maker, client, dry_run=True, limit=None)
    assert stats["pending"] == 1
    assert (
        await db_session.execute(text("SELECT rb_tags FROM stations WHERE slug='needs-tags'"))
    ).scalar_one() is None

    stats = await backfill_tags(maker, client, dry_run=False, limit=None)
    assert (stats["updated"], stats["missing"]) == (1, 0)
    # solo se pidió la emisora sin tags
    assert U2 not in str(route.calls.last.request.url)
    db_session.expire_all()
    rows = dict((await db_session.execute(text("SELECT slug, rb_tags FROM stations"))).all())
    assert rows["needs-tags"] == ["techno", "rock"]
    assert rows["already"] == ["house"]


@respx.mock
async def test_backfill_counts_stations_gone_from_radio_browser(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _insert(db_session, U3, "gone")
    respx.get(url__regex=r"https://host-a\.example/json/stations/byuuid.*").respond(json=[])
    client = RadioBrowserClient(servers=["host-a.example"])
    stats = await backfill_tags(maker, client, dry_run=False, limit=None)
    assert stats["missing"] == 1
    assert (await db_session.execute(text("SELECT rb_tags FROM stations"))).scalar_one() is None


async def test_run_classifies_and_respects_manual_decisions(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _insert(db_session, U1, "electro", tags=["techno", "house"])
    await _insert(db_session, U2, "rocky", tags=["rock", "progressive"])
    await _insert(db_session, U3, "manual-keep", tags=["rock"])
    await db_session.execute(
        text(
            "UPDATE stations SET class_state='accepted', class_source='manual', "
            "electronic_score=100 WHERE slug='manual-keep'",
        ),
    )
    await db_session.commit()

    dry = await run_classification(maker, dry_run=True)
    assert dry["by_state"] == {"accepted": 1, "rejected": 1}
    assert (
        await db_session.execute(text("SELECT count(*) FROM stations WHERE class_state IS NULL"))
    ).scalar_one() == 2

    await run_classification(maker, dry_run=False)
    db_session.expire_all()
    rows = {
        r[0]: (r[1], r[2])
        for r in (
            await db_session.execute(
                text("SELECT slug, class_state, class_source FROM stations"),
            )
        ).all()
    }
    assert rows["electro"] == ("accepted", "rule")
    assert rows["rocky"] == ("rejected", "rule")
    assert rows["manual-keep"] == ("accepted", "manual")


async def test_run_skips_stations_without_collected_tags_and_flags_curated_conflicts(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _insert(db_session, U1, "no-evidence")
    await _insert(db_session, U2, "curated-rock", tags=["rock", "metal"])
    await db_session.execute(text("UPDATE stations SET curated = true WHERE slug='curated-rock'"))
    await db_session.commit()

    report = await run_classification(maker, dry_run=True)
    assert report["classified"] == 1
    assert [c["slug"] for c in report["curated_rejected"]] == ["curated-rock"]


async def test_export_is_read_only_and_includes_verdict(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _insert(db_session, U1, "electro", tags=["techno"])
    await _insert(db_session, U2, "no-evidence")
    rows = await export_rows(maker)
    assert [(r["slug"], r["state"]) for r in rows] == [("electro", "accepted")]
    assert rows[0]["tags"] == ["techno"]
    db_session.expire_all()
    assert (
        await db_session.execute(
            text("SELECT count(*) FROM stations WHERE class_state IS NOT NULL")
        )
    ).scalar_one() == 0
