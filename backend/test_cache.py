import asyncio

from cache import get_cached_embedding, cache_embedding


async def main():
    print("Testing Redis cache...")

    result = await get_cached_embedding("test question")
    print("Initial result:", result)

    test_embedding = [0.1, 0.2, 0.3]

    await cache_embedding(
        "test question",
        test_embedding,
    )

    result = await get_cached_embedding("test question")
    print("Cached result:", result)


if __name__ == "__main__":
    asyncio.run(main())