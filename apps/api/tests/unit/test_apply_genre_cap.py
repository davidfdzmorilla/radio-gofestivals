from __future__ import annotations

from app.repos.stations import apply_genre_cap


def test_empty_input_returns_empty() -> None:
    assert apply_genre_cap([], size=12, cap=2) == []


def test_simple_cap_2_per_bucket() -> None:
    # 4 items in bucket 1, 4 in bucket 2, 4 in bucket 3 — cap=2 keeps 2 each.
    candidates = [
        ("a1", 1), ("a2", 1), ("a3", 1), ("a4", 1),
        ("b1", 2), ("b2", 2), ("b3", 2), ("b4", 2),
        ("c1", 3), ("c2", 3), ("c3", 3), ("c4", 3),
    ]
    result = apply_genre_cap(candidates, size=12, cap=2)
    assert result == ["a1", "a2", "b1", "b2", "c1", "c2"]


def test_preserves_input_order_within_buckets() -> None:
    candidates = [("a", 1), ("b", 1), ("c", 2), ("d", 1), ("e", 2)]
    # 'd' is the 3rd hit on bucket 1 → dropped because cap=2.
    assert apply_genre_cap(candidates, size=10, cap=2) == ["a", "b", "c", "e"]


def test_stops_at_size() -> None:
    candidates = [(f"x{i}", i % 3) for i in range(20)]
    assert len(apply_genre_cap(candidates, size=5, cap=2)) == 5


def test_skips_none_buckets() -> None:
    candidates = [
        ("with-genre", 1),
        ("orphan-1", None),
        ("orphan-2", None),
        ("also-with-genre", 2),
    ]
    assert apply_genre_cap(candidates, size=10, cap=2) == [
        "with-genre", "also-with-genre",
    ]


def test_pool_depleted_returns_partial() -> None:
    candidates = [("a", 1), ("b", 2)]
    assert apply_genre_cap(candidates, size=12, cap=2) == ["a", "b"]


def test_cap_1_strict_diversity() -> None:
    candidates = [("a1", 1), ("a2", 1), ("b1", 2), ("a3", 1), ("c1", 3)]
    assert apply_genre_cap(candidates, size=4, cap=1) == ["a1", "b1", "c1"]


def test_single_bucket_dominates_pool_yields_only_cap_items() -> None:
    # All in bucket 7. cap=2 → only first 2 are kept.
    candidates = [(f"only-{i}", 7) for i in range(10)]
    assert apply_genre_cap(candidates, size=12, cap=2) == ["only-0", "only-1"]
