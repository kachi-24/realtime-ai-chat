import asyncio
import sys
import os
from sqlalchemy import text  # <-- Import the text helper
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Base
from models import User, RefreshToken  # Ensure models are imported

DOCKER_DB_URL = "postgresql+asyncpg://chatuser:chatpassword@db:5432/realtime_chat"


async def init_models():
    print("Connecting internally to database...")
    engine = create_async_engine(DOCKER_DB_URL, echo=True)

    async with engine.begin() as conn:
        # 1. Force enable the vector extension first!
        print("Enabling pgvector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        # 2. Build the tables safely now
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("✅ Database tables created successfully!")


if __name__ == "__main__":
    asyncio.run(init_models())
