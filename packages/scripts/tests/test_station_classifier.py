from __future__ import annotations

import pytest

from scripts.station_classifier import (
    ACCEPT_AT,
    REJECT_AT,
    classify,
    normalize_tags,
    state_for,
)


def test_clear_electronic_station_is_accepted() -> None:
    c = classify(["techno", "house", "electronic"], "Some Radio")
    assert c.state == "accepted"
    assert c.score >= ACCEPT_AT


def test_single_strong_tag_without_negatives_is_accepted() -> None:
    assert classify(["techno"], "Radio X").state == "accepted"


def test_prog_rock_is_not_accepted_through_the_ambiguous_tag() -> None:
    c = classify(["progressive", "rock"], "ProgRock247")
    assert c.state == "rejected"


def test_progressive_alone_is_not_enough() -> None:
    c = classify(["progressive"], "Some Radio")
    assert c.state == "review"


def test_progressive_with_strong_tag_adds_a_bit_and_is_accepted() -> None:
    assert classify(["progressive", "trance"], "Some Radio").state == "accepted"


def test_negative_genres_reject() -> None:
    assert classify(["pop", "news"], "Radio News FM").state == "rejected"


def test_spoken_word_with_chill_tags_is_not_accepted() -> None:
    # caso real: ambient/chillout/lounge junto a documentary/history/culture
    c = classify(["ambient", "chillout", "lounge", "documentary", "history", "culture"], "radiOFF")
    assert c.state != "accepted"


def test_mixed_signals_go_to_review() -> None:
    c = classify(["house", "rock", "pop"], "Radio")
    assert c.state == "review"


def test_no_tags_is_review_not_rejected() -> None:
    c = classify([], "Mystery Radio")
    assert c.state == "review"
    assert "no-tags" in c.reason


def test_name_alone_cannot_accept_or_reject() -> None:
    assert classify([], "Techno Bunker Radio").state == "review"
    assert classify([], "Rock Classic FM").state == "review"


def test_name_breaks_ties_in_the_soft_band() -> None:
    assert (
        classify(["ambient"], "Ambient Techno Radio").score > classify(["ambient"], "Radio").score
    )


def test_soft_tags_alone_stay_in_review() -> None:
    assert classify(["ambient"], "Radio").state == "review"


def test_word_match_not_substring() -> None:
    # "housewives" no es "house"; "pop" dentro de "popular" no es el género pop
    assert classify(["housewives"], "Radio").state == "review"
    assert classify(["popular"], "Radio").state == "review"


def test_multiword_tag_containing_a_term_counts() -> None:
    assert classify(["melodic techno"], "Radio").state == "accepted"


def test_score_is_clamped() -> None:
    assert 0 <= classify(["rock", "metal", "pop", "jazz", "news"], "Rock Radio").score <= 100
    assert classify(["techno", "house", "trance", "dnb", "edm"], "Techno House DJ").score <= 100


def test_normalize_tags_dedupes_caps_and_strips_accents() -> None:
    out = normalize_tags(["  Techno ", "techno", "Électro", ""] + [f"t{i}" for i in range(50)])
    assert out[:2] == ["techno", "electro"]
    assert len(out) == 30


@pytest.mark.parametrize(
    ("score", "state"),
    [
        (ACCEPT_AT, "accepted"),
        (ACCEPT_AT - 1, "review"),
        (REJECT_AT, "rejected"),
        (REJECT_AT + 1, "review"),
    ],
)
def test_state_thresholds(score: int, state: str) -> None:
    assert state_for(score) == state
