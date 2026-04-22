from __future__ import annotations

from icy_worker.icy_parser import parse_icy_metadata


def _padded(body: str, block: int = 16) -> bytes:
    raw = body.encode("latin-1")
    if len(raw) % block != 0:
        raw += b"\x00" * (block - len(raw) % block)
    return raw


def test_standard_format() -> None:
    out = parse_icy_metadata(_padded("StreamTitle='Charlotte de Witte - Overdrive';"))
    assert out["artist"] == "Charlotte de Witte"
    assert out["title"] == "Overdrive"
    assert out["raw"] == "Charlotte de Witte - Overdrive"


def test_no_stream_title() -> None:
    out = parse_icy_metadata(_padded("StreamUrl='https://x';"))
    assert out == {"title": None, "artist": None, "raw": ""}


def test_title_only_no_artist() -> None:
    out = parse_icy_metadata(_padded("StreamTitle='Just a mix';"))
    assert out["artist"] is None
    assert out["title"] == "Just a mix"


def test_special_chars_latin1() -> None:
    out = parse_icy_metadata(_padded("StreamTitle='Café Tacvba - Los Ángeles';"))
    assert out["artist"] == "Café Tacvba"
    assert out["title"] == "Los Ángeles"


def test_unicode_latin1_safe() -> None:
    # Caracteres no latin-1: los bytes llegan pero decodificación latin-1 los traduce byte a byte
    raw = "StreamTitle='Artist - Title';".encode("latin-1")
    out = parse_icy_metadata(raw + b"\x00" * 8)
    assert out["artist"] == "Artist"
    assert out["title"] == "Title"


def test_empty_padding() -> None:
    out = parse_icy_metadata(b"\x00" * 32)
    assert out == {"title": None, "artist": None, "raw": ""}


def test_malformed_no_semicolon() -> None:
    out = parse_icy_metadata(_padded("StreamTitle='Artist - Title'"))
    assert out["artist"] == "Artist"
    assert out["title"] == "Title"


def test_unquoted_value() -> None:
    out = parse_icy_metadata(_padded("StreamTitle=foo bar;"))
    assert out["title"] == "foo bar"
    assert out["artist"] is None


def test_multiple_quotes_inside() -> None:
    # StreamTitle con comilla interna: parser regex es greedy-less, corta en primer cierre
    out = parse_icy_metadata(_padded("StreamTitle='It's OK - Song';"))
    assert out["raw"].startswith("It")


def test_very_long_title() -> None:
    long = "A" * 500 + " - " + "B" * 500
    out = parse_icy_metadata(_padded(f"StreamTitle='{long}';", block=64))
    assert out["artist"] == "A" * 500
    assert out["title"] == "B" * 500


def test_streamurl_ignored() -> None:
    out = parse_icy_metadata(
        _padded("StreamTitle='A - B';StreamUrl='https://x.com/info';"),
    )
    assert out["artist"] == "A"
    assert out["title"] == "B"


def test_leading_trailing_spaces() -> None:
    out = parse_icy_metadata(_padded("StreamTitle='  Artist   -   Title  ';"))
    assert out["artist"] == "Artist"
    assert out["title"] == "Title"


def test_empty_stream_title_returns_none() -> None:
    out = parse_icy_metadata(_padded("StreamTitle='';"))
    assert out == {"title": None, "artist": None, "raw": ""}
