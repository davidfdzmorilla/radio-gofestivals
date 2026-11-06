from __future__ import annotations

from scripts.taxonomy_mapper import GenreRef, map_rb_tags_to_genre_slugs

GENRES = [
    GenreRef(id=1, slug="techno"),
    GenreRef(id=2, slug="house"),
    GenreRef(id=3, slug="deep-house"),
    GenreRef(id=4, slug="tech-house"),
    GenreRef(id=5, slug="dnb"),
    GenreRef(id=6, slug="liquid-dnb"),
    GenreRef(id=7, slug="minimal"),
    GenreRef(id=8, slug="trance"),
    GenreRef(id=9, slug="progressive"),
    GenreRef(id=10, slug="electronic"),
    GenreRef(id=11, slug="ambient"),
]


def _as_dict(matches: list[tuple[int, int]]) -> dict[int, int]:
    return dict(matches)


def test_alias_match() -> None:
    result = _as_dict(map_rb_tags_to_genre_slugs(["drum and bass"], GENRES))
    assert result == {5: 90}


def test_direct_match() -> None:
    result = _as_dict(map_rb_tags_to_genre_slugs(["techno"], GENRES))
    assert result == {1: 100}


def test_fuzzy_match() -> None:
    result = _as_dict(map_rb_tags_to_genre_slugs(["technoo"], GENRES))
    assert 1 in result
    assert result[1] >= 65


def test_skip_short() -> None:
    assert map_rb_tags_to_genre_slugs(["dj"], GENRES) == []


def test_skip_digits() -> None:
    assert map_rb_tags_to_genre_slugs(["123"], GENRES) == []


def test_skip_only_special() -> None:
    assert map_rb_tags_to_genre_slugs(["!!!"], GENRES) == []


def test_dedup_case_and_space() -> None:
    result = _as_dict(
        map_rb_tags_to_genre_slugs(["techno", "Techno", "TECHNO", "  techno  "], GENRES),
    )
    assert result == {1: 100}


def test_best_confidence_wins() -> None:
    result = _as_dict(map_rb_tags_to_genre_slugs(["house", "hous"], GENRES))
    assert result == {2: 100}


def test_unknown_tag_no_match() -> None:
    assert map_rb_tags_to_genre_slugs(["reggaeton"], GENRES) == []


def test_alias_then_exact_uses_higher() -> None:
    result = _as_dict(map_rb_tags_to_genre_slugs(["dnb", "drum and bass"], GENRES))
    assert result[5] == 100


def test_multiple_tags_different_genres() -> None:
    result = _as_dict(
        map_rb_tags_to_genre_slugs(["techno", "deep house", "reggaeton"], GENRES),
    )
    assert result == {1: 100, 3: 90}


def test_unicode_normalization() -> None:
    result = _as_dict(map_rb_tags_to_genre_slugs(["téchno"], GENRES))
    assert 1 in result


def test_ampersand_and_separator_variants_map_to_the_same_genre() -> None:
    assert _as_dict(map_rb_tags_to_genre_slugs(["drum & bass"], GENRES)) == {5: 90}
    assert _as_dict(map_rb_tags_to_genre_slugs(["drum-n-bass"], GENRES)).keys() <= {5}


def test_compound_tags_map_to_their_head_genre_with_lower_confidence() -> None:
    result = _as_dict(map_rb_tags_to_genre_slugs(["melodic techno", "soulful house"], GENRES))
    assert result == {1: 70, 2: 70}


def test_containment_is_by_word_not_substring() -> None:
    assert map_rb_tags_to_genre_slugs(["housewives", "technology"], GENRES) == []


def test_exact_and_alias_beat_containment() -> None:
    assert _as_dict(map_rb_tags_to_genre_slugs(["deep house"], GENRES)) == {3: 90}


def test_new_aliases_need_the_genre_to_exist() -> None:
    assert map_rb_tags_to_genre_slugs(["nu disco"], GENRES) == []
    with_nu = [*GENRES, GenreRef(id=40, slug="nu-disco")]
    assert _as_dict(map_rb_tags_to_genre_slugs(["nu disco"], with_nu)) == {40: 90}


def test_edm_long_form_and_electronic_music_aliases() -> None:
    genres = [*GENRES, GenreRef(id=41, slug="edm")]
    assert _as_dict(map_rb_tags_to_genre_slugs(["electronic dance music"], genres)) == {41: 90}
    assert _as_dict(map_rb_tags_to_genre_slugs(["electronic music"], GENRES)) == {10: 90}


def test_long_tags_are_not_scanned_for_heads() -> None:
    tag = "this is a very long sentence about all the techno parties in town"
    assert map_rb_tags_to_genre_slugs([tag], GENRES) == []
