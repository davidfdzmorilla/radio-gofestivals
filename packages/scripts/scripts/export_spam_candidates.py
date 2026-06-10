from __future__ import annotations

import asyncio
import csv
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


log = get_logger("export_spam_candidates")

app = typer.Typer(help="Export spam-candidate stations to CSV for human review.")


DEFAULT_OUTPUT_DIR = Path(
    os.environ.get("SPAM_REVIEW_OUTPUT_DIR", "tmp/spam_review"),
)

CANDIDATE_QUERY = text(
    """
    SELECT
        s.slug,
        s.name,
        s.country_code,
        s.city,
        s.curated,
        s.quality_score,
        s.votes_local,
        ss.bitrate,
        ss.codec,
        ss.stream_url
    FROM stations s
    LEFT JOIN station_streams ss
        ON ss.station_id = s.id AND ss.is_primary = true
    WHERE
        s.name ~ '[#@_]'
        OR length(s.name) > 60
        OR ss.stream_url LIKE '%?ref=radiobrowser%'
        OR ss.stream_url LIKE '%?ref=rb-%'
    """,
)


CSV_COLUMNS = [
    "slug",
    "name",
    "country_code",
    "city",
    "curated",
    "quality_score",
    "votes_local",
    "bitrate",
    "codec",
    "stream_url",
    "match_reasons",
    "spam_score",
    "suggested_decision",
    "decision",
]


class Candidate(NamedTuple):
    slug: str
    name: str
    country_code: str | None
    city: str | None
    curated: bool
    quality_score: int
    votes_local: int
    bitrate: int | None
    codec: str | None
    stream_url: str | None


# Umbrales del scoring heurístico (ver diagnóstico 2026-05)
NAME_LONG = 80
NAME_MEDIUM = 60
HIDE_THRESHOLD = 7
QUALITY_TRUSTED = 70
REVIEW_THRESHOLD = 3
NAME_PREVIEW = 110
BASELINE_TOTAL = 156
BASELINE_CURATED = 44
BASELINE_DRIFT_MAX = 10


def compute_spam_score(
    name: str,
    stream_url: str | None,
    curated: bool,
    quality_score: int,
) -> tuple[int, list[str]]:
    """Return (score, reasons). Score range roughly -4..+12.

    Mirrors the rubric from the spam-review ticket verbatim. The reasons list
    is preserved in insertion order so the CSV reader can see exactly which
    signals fired.
    """
    score = 0
    reasons: list[str] = []
    name_upper = name.upper()
    url = stream_url or ""

    if re.match(r"^[#*>\-]\s", name):
        score += 3
        reasons.append("prefix_suspicious")
    if name.startswith("__"):
        score += 3
        reasons.append("double_underscore_prefix")

    if ">>" in name or "<<" in name:
        score += 2
        reasons.append("bracket_chain")
    if "@" in name:
        score += 2
        reasons.append("contains_at")
    if "TOP 100" in name_upper or "TOP100" in name_upper:
        score += 2
        reasons.append("top_100")
    if "CHARTS" in name_upper:
        score += 2
        reasons.append("charts_keyword")
    if "NON-STOP" in name_upper or "NONSTOP" in name_upper:
        score += 2
        reasons.append("non_stop_keyword")
    if len(name) > NAME_LONG:
        score += 2
        reasons.append("len_gt_80")

    if NAME_MEDIUM < len(name) <= NAME_LONG:
        score += 1
        reasons.append("len_60_80")
    if "?ref=radiobrowser-" in url:
        if re.search(r"\?ref=radiobrowser-\w+", url):
            score += 2
            reasons.append("ref_radiobrowser_promo")
        else:
            score += 1
            reasons.append("ref_radiobrowser")
    if "?ref=rb-" in url:
        score += 1
        reasons.append("ref_rb_promo")

    if curated:
        score -= 3
        reasons.append("curated_minus3")
    if quality_score >= QUALITY_TRUSTED:
        score -= 1
        reasons.append("qs_gte_70_minus1")

    return score, reasons


def suggest_decision(score: int) -> str:
    if score >= HIDE_THRESHOLD:
        return "hide"
    if score >= REVIEW_THRESHOLD:
        return "review"
    return "keep"


async def fetch_candidates(session: AsyncSession) -> list[Candidate]:
    result = await session.execute(CANDIDATE_QUERY)
    return [
        Candidate(
            slug=str(row[0]),
            name=str(row[1]),
            country_code=row[2],
            city=row[3],
            curated=bool(row[4]),
            quality_score=int(row[5] or 0),
            votes_local=int(row[6] or 0),
            bitrate=row[7],
            codec=row[8],
            stream_url=row[9],
        )
        for row in result.all()
    ]


def annotate(c: Candidate) -> tuple[int, list[str], str]:
    """Return (score, reasons_with_extra, suggested_decision)."""
    score, reasons = compute_spam_score(
        c.name,
        c.stream_url,
        c.curated,
        c.quality_score,
    )
    if c.stream_url is None:
        reasons.append("no_primary_stream")
    return score, reasons, suggest_decision(score)


def _write_csv(path: Path, rows: list[Candidate]) -> int:
    """Write CSV with QUOTE_MINIMAL, errors='replace' for unrepresentable bytes.

    Returns count of rows that needed an encoding substitution so the caller
    can surface it.
    """
    substituted = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", errors="replace", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(CSV_COLUMNS)
        for c in rows:
            try:
                c.name.encode("utf-8")
            except UnicodeEncodeError:
                substituted += 1
            score, reasons, suggested = annotate(c)
            writer.writerow(
                [
                    c.slug,
                    c.name,
                    c.country_code or "",
                    c.city or "",
                    "true" if c.curated else "false",
                    c.quality_score,
                    c.votes_local,
                    c.bitrate if c.bitrate is not None else "",
                    c.codec or "",
                    c.stream_url or "",
                    "|".join(reasons),
                    score,
                    suggested,
                    "",
                ]
            )
    return substituted


CANONICAL_VERIFY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("hash_top_100_curated", "# TOP 100 CLUB CHARTS"),
    ("double_underscore_curated", "__CLUB__ by rautemusik"),
    ("uzic_ch_long_name", "UZIC.CH :: TECHNO"),
)


def _find_one(
    candidates: list[Candidate],
    needle: str,
) -> Candidate | None:
    needle_low = needle.lower()
    for c in candidates:
        if needle_low in c.name.lower():
            return c
    return None


def _print_verify(candidates: list[Candidate]) -> None:
    print("Canonical verification:")
    for label, needle in CANONICAL_VERIFY_PATTERNS:
        c = _find_one(candidates, needle)
        if c is None:
            print(f"  [{label}] NOT FOUND in pool — needle='{needle}'")
            continue
        score, reasons, suggested = annotate(c)
        print(f"  [{label}]")
        print(f"    name   : {c.name[:NAME_PREVIEW]}{'…' if len(c.name) > NAME_PREVIEW else ''}")
        print(f"    slug   : {c.slug}")
        print(f"    curated: {c.curated}   quality_score: {c.quality_score}")
        print(f"    url    : {(c.stream_url or '<none>')[:NAME_PREVIEW]}")
        print(f"    score  : {score}   suggested: {suggested}")
        print(f"    reasons: {'|'.join(reasons)}")


async def _run(*, verify_only: bool, output_dir: Path) -> None:
    print("Querying candidates...")
    engine = make_engine()
    maker: async_sessionmaker[AsyncSession] = make_sessionmaker(engine)
    try:
        async with maker() as session:
            candidates = await fetch_candidates(session)
    finally:
        await engine.dispose()

    total = len(candidates)
    curated = [c for c in candidates if c.curated]
    print(f"  Total candidates: {total}")
    print(f"  Of which curated: {len(curated)}")
    print()

    annotated = [(c, *annotate(c)) for c in candidates]
    hide_n = sum(1 for _, s, _r, _sd in annotated if s >= HIDE_THRESHOLD)
    review_n = sum(1 for _, s, _r, _sd in annotated if REVIEW_THRESHOLD <= s < HIDE_THRESHOLD)
    keep_n = sum(1 for _, s, _r, _sd in annotated if s < REVIEW_THRESHOLD)

    print("Score distribution:")
    print(f"  hide   (>=7): {hide_n}")
    print(f"  review (3-6): {review_n}")
    print(f"  keep   (<3):  {keep_n}")
    print()

    if verify_only:
        _print_verify(candidates)
        return

    # Drift guard: ticket says abort if the headline counts diverge >10
    # from the diagnostic (156 total / 44 curated).
    drift_total = abs(total - BASELINE_TOTAL)
    drift_curated = abs(len(curated) - BASELINE_CURATED)
    if drift_total > BASELINE_DRIFT_MAX or drift_curated > BASELINE_DRIFT_MAX:
        print(
            f"ABORT: counts drifted from diagnostic baseline "
            f"(total {total} vs {BASELINE_TOTAL}, curated {len(curated)} vs {BASELINE_CURATED}). "
            f"Re-run diagnosis before exporting.",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    curated_sorted = sorted(
        curated,
        key=lambda c: (-c.quality_score, c.name),
    )
    all_sorted = sorted(
        candidates,
        key=lambda c: (
            -compute_spam_score(c.name, c.stream_url, c.curated, c.quality_score)[0],
            -c.quality_score,
            c.name,
        ),
    )

    curated_path = output_dir / "spam_candidates_curated.csv"
    all_path = output_dir / "spam_candidates_all.csv"

    print(f"Writing {curated_path} ({len(curated_sorted)} rows)")
    sub_c = _write_csv(curated_path, curated_sorted)
    print(f"Writing {all_path} ({len(all_sorted)} rows)")
    sub_a = _write_csv(all_path, all_sorted)

    if sub_c or sub_a:
        print(
            f"Note: {sub_c + sub_a} row(s) needed an encoding substitution "
            f"(non-UTF-8 bytes in name).",
        )

    print()
    print("Done. Review CSVs and fill the 'decision' column with one of: hide, keep, defer.")


@app.command("run")
def cmd_run(
    verify_only: bool = typer.Option(  # noqa: FBT001,FBT002
        False,
        "--verify-only",
        help="Print canonical row scores and exit without writing CSVs.",
    ),
    output_dir: Path = typer.Option(
        DEFAULT_OUTPUT_DIR,
        "--output-dir",
        help="Where to write CSVs (default: tmp/spam_review; $SPAM_REVIEW_OUTPUT_DIR).",
    ),
) -> None:
    asyncio.run(_run(verify_only=verify_only, output_dir=output_dir))


if __name__ == "__main__":
    app()
