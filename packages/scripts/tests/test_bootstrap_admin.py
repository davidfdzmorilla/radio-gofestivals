from __future__ import annotations

from typing import TYPE_CHECKING

import bcrypt
import pytest
from sqlalchemy import text

from scripts.bootstrap_admin import _run, hash_password_sync

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def test_creates_admin(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _run(maker, "new@test.com", "superstrong1", "New Admin")

    row = (
        await db_session.execute(
            text("SELECT email, name, active, password_hash FROM admins WHERE email='new@test.com'"),
        )
    ).first()
    assert row is not None
    assert row[0] == "new@test.com"
    assert row[1] == "New Admin"
    assert row[2] is True
    assert bcrypt.checkpw(b"superstrong1", row[3].encode("utf-8"))


async def test_password_hash_never_stores_plaintext(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    plain = "superstrong2"
    await _run(maker, "user@test.com", plain, None)
    ph = (
        await db_session.execute(
            text("SELECT password_hash FROM admins WHERE email='user@test.com'"),
        )
    ).scalar_one()
    assert plain not in ph
    assert ph.startswith("$2")


async def test_fails_if_exists(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO admins (email, password_hash, name)
            VALUES ('dup@test.com', :ph, 'Dup')
            """,
        ),
        {"ph": hash_password_sync("original123")},
    )
    await db_session.commit()

    with pytest.raises(SystemExit):
        await _run(maker, "dup@test.com", "other123456", "Other")
