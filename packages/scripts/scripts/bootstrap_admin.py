from __future__ import annotations

import asyncio
import getpass
import sys
from typing import TYPE_CHECKING

import bcrypt
import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


log = get_logger("bootstrap_admin")
app = typer.Typer(help="Crea el primer admin del sistema.")


MIN_PASSWORD_LENGTH = 10


def hash_password_sync(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


async def _exists(session: AsyncSession, email: str) -> bool:
    row = (
        await session.execute(
            text("SELECT 1 FROM admins WHERE email = :email"),
            {"email": email.lower()},
        )
    ).first()
    return row is not None


async def _insert(session: AsyncSession, email: str, password_hash: str, name: str | None) -> str:
    result = await session.execute(
        text(
            """
            INSERT INTO admins (email, password_hash, name)
            VALUES (:email, :ph, :name)
            RETURNING id::text
            """,
        ),
        {"email": email.lower(), "ph": password_hash, "name": name},
    )
    admin_id = result.scalar_one()
    await session.commit()
    return str(admin_id)


async def _run(
    maker: async_sessionmaker[AsyncSession],
    email: str,
    password: str,
    name: str | None,
) -> None:
    async with maker() as session:
        if await _exists(session, email):
            log.error("admin_exists", email=email)
            sys.exit(1)
        admin_id = await _insert(session, email, hash_password_sync(password), name)
    log.info("admin_created", admin_id=admin_id, email=email)


@app.command()
def create(
    email: str = typer.Option(..., "--email", help="Email del admin"),
    name: str | None = typer.Option(None, "--name", help="Nombre visible (opcional)"),
    password: str | None = typer.Option(
        None,
        "--password",
        help="Contraseña (omitir para prompt interactivo). Evita usar en scripts con historial.",
    ),
) -> None:
    pw = password
    if pw is None:
        pw = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm:  ")
        if pw != confirm:
            typer.echo("ERROR: passwords don't match", err=True)
            raise typer.Exit(code=2)
    if len(pw) < MIN_PASSWORD_LENGTH:
        typer.echo(f"ERROR: password must be at least {MIN_PASSWORD_LENGTH} chars", err=True)
        raise typer.Exit(code=2)

    engine = make_engine()
    maker = make_sessionmaker(engine)

    async def _main() -> None:
        try:
            await _run(maker, email, pw, name)
        finally:
            await engine.dispose()

    asyncio.run(_main())


if __name__ == "__main__":
    app()
