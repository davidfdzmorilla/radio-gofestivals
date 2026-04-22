from __future__ import annotations

import secrets

import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE_KW = {
    "database_url": "postgresql+asyncpg://u:p@h:5432/d",
    "redis_url": "redis://h:6379/0",
    "rb_user_agent": "radio.gofestivals/test (admin@gofestivals.eu)",
    "_env_file": None,
}


def _settings(**overrides: object) -> Settings:
    kwargs = {**BASE_KW, **overrides}
    return Settings(**kwargs)  # type: ignore[arg-type]


def test_dev_allows_weak_secret() -> None:
    s = _settings(env="dev", jwt_secret="x")
    assert s.env == "dev"
    assert s.jwt_secret.get_secret_value() == "x"


def test_prod_rejects_short_secret() -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(env="prod", jwt_secret="abc")
    assert "at least 32 chars" in str(exc.value)


def test_prod_rejects_change_me() -> None:
    bad = "change_me_" + "a" * 40
    with pytest.raises(ValidationError) as exc:
        _settings(env="prod", jwt_secret=bad)
    assert "forbidden placeholder" in str(exc.value)


def test_prod_accepts_strong_secret() -> None:
    strong = secrets.token_hex(32)
    s = _settings(env="prod", jwt_secret=strong)
    assert s.jwt_secret.get_secret_value() == strong


def test_staging_also_validates() -> None:
    with pytest.raises(ValidationError):
        _settings(env="staging", jwt_secret="short")


def test_prod_rejects_example_user_agent() -> None:
    strong = secrets.token_hex(32)
    with pytest.raises(ValidationError) as exc:
        _settings(
            env="prod",
            jwt_secret=strong,
            rb_user_agent="radio.gofestivals/0.1 (admin@example.com)",
        )
    assert "placeholder" in str(exc.value)


def test_prod_accepts_real_user_agent() -> None:
    strong = secrets.token_hex(32)
    s = _settings(
        env="prod",
        jwt_secret=strong,
        rb_user_agent="radio.gofestivals/0.1 (admin@gofestivals.eu)",
    )
    assert s.rb_user_agent.endswith("(admin@gofestivals.eu)")


def test_error_message_does_not_leak_secret() -> None:
    leaky = "change_me_" + "X" * 40
    with pytest.raises(ValidationError) as exc:
        _settings(env="prod", jwt_secret=leaky)
    rendered = str(exc.value)
    assert leaky not in rendered
    assert "XXXX" not in rendered
