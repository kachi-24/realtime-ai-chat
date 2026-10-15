from logging.config import fileConfig

import asyncio
import os
import sys

from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context


# =========================================================
# PATH
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[1]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# =========================================================
# APPLICATION IMPORTS
# =========================================================

from database import Base
from models import (
    User,
    EmailVerificationToken,
    RefreshToken,
    Conversation,
    Message,
    Document,
    DocumentChunk,
)


# =========================================================
# ALEMBIC CONFIG
# =========================================================

config = context.config


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


# =========================================================
# DATABASE URL (Dynamic Docker/Local Detector)
# =========================================================

# If the file '.dockerenv' exists, we are running inside the container
IS_DOCKER = os.path.exists("/.dockerenv")

DB_HOST = "db" if IS_DOCKER else "localhost"
DB_PORT = "5432" if IS_DOCKER else "5433"

DATABASE_URL = (
    f"postgresql+asyncpg://"
    f"chatuser:chatpassword"
    f"@{DB_HOST}:{DB_PORT}/realtime_chat"
)


config.set_main_option(
    "sqlalchemy.url",
    DATABASE_URL.replace("%", "%%"),
)


# =========================================================
# OFFLINE MIGRATION
# =========================================================

def run_migrations_offline() -> None:

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
    )

    with context.begin_transaction():

        context.run_migrations()


# =========================================================
# ONLINE MIGRATION
# =========================================================

def do_run_migrations(
    connection: Connection,
) -> None:

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():

        context.run_migrations()


async def run_async_migrations() -> None:

    connectable = async_engine_from_config(
        config.get_section(
            config.config_ini_section,
            {}
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:

        await connection.run_sync(
            do_run_migrations
        )

    await connectable.dispose()


def run_migrations_online() -> None:

    asyncio.run(
        run_async_migrations()
    )


# =========================================================
# RUN
# =========================================================

if context.is_offline_mode():

    run_migrations_offline()

else:

    run_migrations_online()
