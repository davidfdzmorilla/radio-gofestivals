from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

import httpx
import respx
from sqlalchemy import text

from scripts.classify_cmd import (
    add_evidence,
    apply_llm_verdicts,
    backfill_tags,
    evidence_hash,
    export_rows,
    llm_candidates,
    llm_outcome,
    relink_genres,
    run_classification,
)
from scripts.rb_client import RadioBrowserClient
from scripts.rb_sync import run_sync

if TYPE_CHECKING:
    import pytest
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


async def test_relink_genres_rewrites_only_rb_tag_links(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _insert(db_session, U1, "compound", tags=["melodic techno", "rock"])
    await _insert(db_session, U2, "no-tags-yet")  # rb_tags NULL: no se toca
    techno = (
        await db_session.execute(text("SELECT id FROM genres WHERE slug='techno'"))
    ).scalar_one()
    house = (
        await db_session.execute(text("SELECT id FROM genres WHERE slug='house'"))
    ).scalar_one()
    await db_session.execute(
        text(
            "INSERT INTO station_genres (station_id, genre_id, source, confidence) "
            "SELECT id, :g, 'manual', 100 FROM stations WHERE slug='compound'",
        ),
        {"g": house},
    )
    trance = (
        await db_session.execute(text("SELECT id FROM genres WHERE slug='trance'"))
    ).scalar_one()
    await db_session.execute(  # enlace rb_tag obsoleto: debe desaparecer
        text(
            "INSERT INTO station_genres (station_id, genre_id, source, confidence) "
            "SELECT id, :g, 'rb_tag', 50 FROM stations WHERE slug='compound'",
        ),
        {"g": trance},
    )
    await db_session.commit()

    dry = await relink_genres(maker, dry_run=True)
    assert dry["changed"] == 1
    assert (
        await db_session.execute(text("SELECT count(*) FROM station_genres WHERE source='rb_tag'"))
    ).scalar_one() == 1

    await relink_genres(maker, dry_run=False)
    db_session.expire_all()
    rows = (
        await db_session.execute(
            text("SELECT genre_id, source FROM station_genres ORDER BY source")
        )
    ).all()
    assert sorted(rows) == sorted([(house, "manual"), (techno, "rb_tag")])
    again = await relink_genres(maker, dry_run=False)
    assert again["changed"] == 0


# --- Fase 2: segundo clasificador (veredictos del modelo) -------------------------------------


async def _state(db: AsyncSession, slug: str) -> tuple[Any, ...]:
    db.expire_all()
    row = (
        await db.execute(
            text(
                "SELECT class_state, class_source, electronic_score, class_evidence "
                "FROM stations WHERE slug = :s",
            ),
            {"s": slug},
        )
    ).first()
    assert row is not None
    return tuple(row)


def test_llm_outcome_needs_confidence_to_decide() -> None:
    assert llm_outcome("electronic", 90) == ("accepted", 90)
    assert llm_outcome("not_electronic", 90) == ("rejected", 10)
    assert llm_outcome("electronic", 69) == ("review", 50)
    assert llm_outcome("not_electronic", 40) == ("review", 50)
    assert llm_outcome("unsure", 99) == ("review", 50)
    assert llm_outcome("electronic", 500) == ("accepted", 100)


async def test_candidates_are_the_review_band_plus_curated_conflicts(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _insert(db_session, U1, "in-review", tags=["house", "rock", "pop"])
    await _insert(db_session, "00000000-0000-0000-0000-0000000000b1", "clear-yes", tags=["techno"])
    await _insert(db_session, "00000000-0000-0000-0000-0000000000b2", "clear-no", tags=["rock"])
    await _insert(db_session, "00000000-0000-0000-0000-0000000000b3", "curated-no", tags=["rock"])
    await db_session.execute(text("UPDATE stations SET curated = true WHERE slug = 'curated-no'"))
    await db_session.commit()
    slugs = [c["slug"] for c in await llm_candidates(maker, limit=10)]
    assert sorted(slugs) == ["curated-no", "in-review"]


async def test_candidates_skip_manual_hidden_inactive_and_already_judged(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    tags = ["house", "rock", "pop"]
    for i, slug in enumerate(["manual", "hidden", "inactive", "judged", "fresh"]):
        await _insert(db_session, f"00000000-0000-0000-0000-0000000000c{i}", slug, tags=tags)
    await db_session.execute(text("UPDATE stations SET class_source='manual' WHERE slug='manual'"))
    await db_session.execute(text("UPDATE stations SET hidden = true WHERE slug='hidden'"))
    await db_session.execute(text("UPDATE stations SET status = 'broken' WHERE slug='inactive'"))
    await db_session.execute(
        text("UPDATE stations SET class_source='llm', class_evidence=:h WHERE slug='judged'"),
        {"h": evidence_hash("judged", tags)},
    )
    await db_session.commit()
    assert [c["slug"] for c in await llm_candidates(maker, limit=10)] == ["fresh"]


async def test_candidates_come_back_when_the_evidence_changed_and_respect_limit(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _insert(db_session, U1, "judged", tags=["house", "rock", "pop"])
    await db_session.execute(
        text("UPDATE stations SET class_source='llm', class_evidence='stale' WHERE slug='judged'"),
    )
    await _insert(db_session, U2, "other", tags=["house", "rock", "pop"])
    await db_session.commit()
    assert len(await llm_candidates(maker, limit=10)) == 2
    assert len(await llm_candidates(maker, limit=1)) == 1


async def test_apply_writes_valid_verdicts_and_discards_the_rest(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    for i, slug in enumerate(["yes", "no", "meh", "manual"]):
        await _insert(
            db_session, f"00000000-0000-0000-0000-0000000000d{i}", slug, tags=["house", "rock"]
        )
    await db_session.execute(text("UPDATE stations SET class_source='manual' WHERE slug='manual'"))
    await db_session.commit()
    results = [
        {"slug": "yes", "verdict": "electronic", "confidence": 90, "reason": "eje house"},
        {"slug": "no", "verdict": "not_electronic", "confidence": 80, "reason": "rock"},
        {"slug": "meh", "verdict": "electronic", "confidence": 50, "reason": "poco claro"},
        {"slug": "manual", "verdict": "not_electronic", "confidence": 99, "reason": "x"},
        {"slug": "ghost", "verdict": "electronic", "confidence": 99, "reason": "x"},
        {"slug": "yes", "verdict": "banana", "confidence": 99, "reason": "x"},
        {"slug": "yes", "verdict": "electronic", "confidence": "high", "reason": "x"},
        {"verdict": "electronic", "confidence": 90},
    ]
    dry = await apply_llm_verdicts(maker, results, dry_run=True)
    assert (await _state(db_session, "yes"))[1] is None  # el ensayo no escribe
    stats = await apply_llm_verdicts(maker, results, dry_run=False)
    assert (stats["applied"], stats["unknown"], stats["invalid"], stats["manual"]) == (3, 1, 3, 1)
    assert dry["applied"] == stats["applied"]
    assert (await _state(db_session, "yes"))[:3] == ("accepted", "llm", 90)
    assert (await _state(db_session, "no"))[:3] == ("rejected", "llm", 20)
    assert (await _state(db_session, "meh"))[:3] == ("review", "llm", 50)
    assert (await _state(db_session, "manual"))[1] == "manual"
    assert (await _state(db_session, "yes"))[3] == evidence_hash("yes", ["house", "rock"])


async def test_rules_rerun_keeps_a_current_llm_verdict_but_overrides_a_stale_one(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _insert(db_session, U1, "current", tags=["house", "rock", "pop"])
    await _insert(db_session, U2, "stale", tags=["house", "rock", "pop"])
    await apply_llm_verdicts(
        maker,
        [
            {"slug": "current", "verdict": "electronic", "confidence": 95, "reason": "x"},
            {"slug": "stale", "verdict": "electronic", "confidence": 95, "reason": "x"},
        ],
        dry_run=False,
    )
    await db_session.execute(
        text("UPDATE stations SET rb_tags = :t WHERE slug = 'stale'"),
        {"t": ["rock", "pop", "house"]},
    )
    await db_session.commit()

    report = await run_classification(maker, dry_run=False)
    assert report["by_state"].get("llm_kept") == 1
    assert (await _state(db_session, "current"))[:2] == ("accepted", "llm")
    assert (await _state(db_session, "stale"))[1] == "rule"


# --- Fase 2b: evidencia (web y últimos temas) ---------------------------------------------------


async def _station_with(
    db: AsyncSession,
    uuid: str,
    slug: str,
    *,
    homepage: str | None = None,
    tracks: list[tuple[str, str]] | None = None,
) -> None:
    await _insert(db, uuid, slug, tags=["house", "rock", "pop"])
    await db.execute(
        text("UPDATE stations SET homepage_url = :h WHERE slug = :s"),
        {"h": homepage, "s": slug},
    )
    for artist, title in tracks or []:
        await db.execute(
            text(
                "INSERT INTO now_playing (station_id, artist, title) "
                "SELECT id, :a, :t FROM stations WHERE slug = :s",
            ),
            {"a": artist, "t": title, "s": slug},
        )
    await db.commit()


@respx.mock
async def test_add_evidence_attaches_web_and_tracks_and_strips_internal_fields(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _station_with(
        db_session,
        U1,
        "rich",
        homepage="https://rich.example/",
        tracks=[("Daft Punk", "One More Time"), ("Daft Punk", "One More Time")],
    )
    respx.get("https://rich.example/").respond(
        200,
        html='<title>Rich Radio</title><meta name="description" content="Techno 24/7">',
    )
    candidates = await llm_candidates(maker, limit=10)
    assert {"_id", "_homepage"} <= set(candidates[0])
    async with httpx.AsyncClient() as client:
        out = await add_evidence(maker, candidates, client)
    assert out == [
        {
            "slug": "rich",
            "name": "rich",
            "country": None,
            "tags": ["house", "rock", "pop"],
            "web": {"title": "Rich Radio", "description": "Techno 24/7"},
            "ultimos_temas": ["Daft Punk - One More Time"],
        },
    ]


@respx.mock
async def test_add_evidence_is_optional_and_a_broken_site_never_fails_the_run(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _station_with(db_session, U1, "down", homepage="https://down.example/")
    await _station_with(db_session, U2, "nothing")
    respx.get("https://down.example/").mock(side_effect=httpx.ConnectError("boom"))
    candidates = await llm_candidates(maker, limit=10)
    async with httpx.AsyncClient() as client:
        out = await add_evidence(maker, candidates, client)
    assert sorted(o["slug"] for o in out) == ["down", "nothing"]
    assert all("web" not in o and "ultimos_temas" not in o for o in out)
    assert all(not k.startswith("_") for o in out for k in o)


async def test_add_evidence_with_no_candidates_makes_no_queries(
    maker: async_sessionmaker[AsyncSession],
) -> None:
    async with httpx.AsyncClient() as client:
        assert await add_evidence(maker, [], client) == []


def test_evidence_hash_depends_on_the_evidence_version(monkeypatch: pytest.MonkeyPatch) -> None:
    before = evidence_hash("Radio", ["house"])
    monkeypatch.setattr("scripts.classify_cmd.EVIDENCE_VERSION", "v3")
    assert evidence_hash("Radio", ["house"]) != before


async def test_verdicts_from_an_older_evidence_version_are_asked_again(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _insert(db_session, U1, "old-verdict", tags=["house", "rock", "pop"])
    await db_session.execute(
        text("UPDATE stations SET class_source='llm', class_evidence=:h WHERE slug='old-verdict'"),
        {"h": hashlib.sha1(b"name+tags sin version", usedforsecurity=False).hexdigest()[:16]},  # noqa: S324
    )
    await db_session.commit()
    assert [c["slug"] for c in await llm_candidates(maker, limit=10)] == ["old-verdict"]


async def test_add_evidence_survives_an_unexpected_error_fetching_a_site(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*_a: object, **_k: object) -> None:
        msg = "inesperado"
        raise RuntimeError(msg)

    monkeypatch.setattr("scripts.classify_cmd.fetch_page_info", boom)
    await _station_with(db_session, U1, "weird", homepage="https://weird.example/")
    candidates = await llm_candidates(maker, limit=10)
    async with httpx.AsyncClient() as client:
        out = await add_evidence(maker, candidates, client)
    assert [o["slug"] for o in out] == ["weird"]
