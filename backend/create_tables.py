import asyncio

from database import engine, Base

# Import models so their classes register themselves on Base.metadata
# before create_all runs. Without this import, Base.metadata would be
# empty and create_all would silently create nothing.
import models  # noqa: F401


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully.")


if __name__ == "__main__":
    asyncio.run(create_tables())