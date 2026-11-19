"""Explicitly change a user's password and close all sessions.

Example (from ``backend``)::

    .venv/bin/python -m scripts.set_password --email admin@example.org

The password is read interactively unless ``--password`` is supplied for
automation. The command never prints the password or the hash.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from app.config import Settings
from app.db.database import Database
from app.repositories.postgres.users import PgUserRepository
from app.services.security import PasswordService, is_valid_password, normalize_email


def parse_args() -> argparse.Namespace:
    """Reads the target email and optional non-interactive password."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", help="email of an existing user (default: ADMIN_EMAIL)")
    parser.add_argument("--password", help="new password; omit to be prompted without echo")
    return parser.parse_args()


async def change(email: str, password: str) -> int:
    """Validates and stores a new password, invalidating every session."""
    if not is_valid_password(password):
        print("Пароль должен содержать не менее 8 символов, буквы и цифры", file=sys.stderr)
        return 2
    settings = Settings()
    database = Database(settings.database_url, settings.db_pool_min, settings.db_pool_max)
    await database.connect()
    try:
        users = PgUserRepository(database)
        user = await users.get_by_email(normalize_email(email))
        if user is None:
            print("Пользователь с таким адресом не найден", file=sys.stderr)
            return 1
        password_hash = await asyncio.to_thread(PasswordService(fast=False).hash, password)
        await users.update_password_hash(user.id, password_hash)
        await database.pool.execute("DELETE FROM user_session WHERE user_id=$1", user.id)
        print("Пароль обновлён, все сессии закрыты")
        return 0
    finally:
        await database.close()


def main() -> None:
    """Entry point."""
    args = parse_args()
    email = args.email or Settings().admin_email
    if not email:
        raise SystemExit("Укажите --email или ADMIN_EMAIL")
    password = args.password or getpass.getpass("Новый пароль: ")
    if not args.password:
        confirmation = getpass.getpass("Повторите пароль: ")
        if password != confirmation:
            raise SystemExit("Пароли не совпадают")
    raise SystemExit(asyncio.run(change(email, password)))


if __name__ == "__main__":
    main()
