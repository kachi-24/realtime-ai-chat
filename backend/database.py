import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# ============================================================
# Load .env from the project root, not just the current
# working directory. A bare load_dotenv() only checks cwd,
# which silently fails whenever this module (or anything that
# imports it, like create_tables.py) is run from inside
# backend/ instead of the project root — same failure mode
# that broke JWT_SECRET_KEY loading earlier. Resolving the
# path relative to this file's own location makes it work no
# matter which directory you run from.
# ============================================================
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")


engine = create_async_engine(
    DATABASE_URL,
    echo=True,
)


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session