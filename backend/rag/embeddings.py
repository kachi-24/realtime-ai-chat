import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
import httpx

from cache import (
    get_cached_embedding,
    cache_embedding,
)

# Same reasoning as redis_client.py / redis_queue.py /
# database.py: resolve .env relative to this file's location,
# and read the Ollama URL from the environment instead of
# hardcoding "localhost" — inside the backend/worker
# containers, "localhost" refers to the container itself, not
# the Windows host where Ollama is actually running.
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

OLLAMA_EMBED_URL = os.getenv(
    "OLLAMA_EMBED_URL",
    "http://localhost:11434/api/embed",
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "nomic-embed-text",
)

# --------------------------------------------------------
# How long to wait for a single embedding call before
# giving up. Without this, a hung Ollama request looks
# identical to a slow one — the app just sits there
# forever with no error and no way to tell what's wrong.
# --------------------------------------------------------

EMBEDDING_TIMEOUT_SECONDS = 60.0

# --------------------------------------------------------
# How many chunks to embed at the same time. Keep this
# modest on CPU-only setups — real parallelism is limited
# by CPU cores, so a high number mostly adds overhead
# rather than speed.
# --------------------------------------------------------

MAX_CONCURRENT_EMBEDDINGS = 2


async def _embed_via_ollama(
    text: str,
    client: httpx.AsyncClient,
) -> list[float]:
    """
    Sends a single embedding request using the given
    client. The caller owns the client's lifecycle.
    """

    payload = {
        "model": EMBEDDING_MODEL,
        "input": text,
        # Keep the model loaded in memory for a while
        # after this call, so the *next* chunk doesn't
        # pay the cold-start cost of reloading it.
        # NOTE: this machine is memory-constrained
        # (CPU-only, integrated graphics, limited RAM).
        # Keeping the embedding model loaded for 30
        # minutes was competing for RAM with the chat
        # model (qwen3:1.7b) whenever both were needed
        # close together, causing Ollama to fail to
        # allocate memory for the chat model. Unload
        # the embedding model immediately after each
        # call instead.
        "keep_alive": "0",
    }

    try:

        response = await client.post(
            OLLAMA_EMBED_URL,
            json=payload,
        )

        response.raise_for_status()

    except httpx.TimeoutException as error:

        raise TimeoutError(
            f"Ollama did not respond within "
            f"{EMBEDDING_TIMEOUT_SECONDS} seconds. "
            f"Is Ollama running and is "
            f"'{EMBEDDING_MODEL}' pulled? "
            f"({error})"
        )

    except httpx.ConnectError as error:

        raise ConnectionError(
            f"Could not connect to Ollama at "
            f"{OLLAMA_EMBED_URL}. Is Ollama running? "
            f"({error})"
        )

    data = response.json()

    embeddings = data.get("embeddings")

    if not embeddings:

        raise ValueError(
            "Ollama returned no embedding"
        )

    return embeddings[0]


async def create_embedding(
    text: str,
) -> list[float]:
    """
    Embeds a single piece of text. Opens and closes its
    own short-lived client, scoped to this call only.

    IMPORTANT: do not hoist an httpx.AsyncClient to
    module level and reuse it across calls. This function
    may be invoked from different asyncio.run() calls
    (e.g. once per RQ job), each of which creates a new
    event loop. A client created in one event loop breaks
    when reused from a different one — it doesn't error
    cleanly, it just hangs or gets very slow. Always
    create the client fresh within the active event loop.
    """

    # -----------------------------------------
    # 1. Check Redis cache
    # -----------------------------------------

    cached_embedding = await get_cached_embedding(text)

    if cached_embedding is not None:

        print("Redis cache HIT")

        return cached_embedding

    # -----------------------------------------
    # 2. Cache miss — call Ollama
    # -----------------------------------------

    print("Redis cache MISS")

    async with httpx.AsyncClient(
        timeout=EMBEDDING_TIMEOUT_SECONDS
    ) as client:

        embedding = await _embed_via_ollama(
            text,
            client,
        )

    # -----------------------------------------
    # 3. Store embedding in Redis
    # -----------------------------------------

    await cache_embedding(
        text,
        embedding,
    )

    print("Embedding stored in Redis")

    return embedding


async def create_embeddings_batch(
    texts: list[str],
) -> list[list[float]]:
    """
    Embeds multiple chunks concurrently, reusing a single
    client for the duration of this batch only. This is
    safe because the whole batch runs within one call —
    and therefore one event loop — so the client never
    crosses an asyncio.run() boundary.
    """

    semaphore = asyncio.Semaphore(
        MAX_CONCURRENT_EMBEDDINGS
    )

    async with httpx.AsyncClient(
        timeout=EMBEDDING_TIMEOUT_SECONDS
    ) as client:

        async def embed_one(text: str):

            # -----------------------------------
            # Check cache first, per chunk, same
            # as create_embedding does.
            # -----------------------------------

            cached_embedding = (
                await get_cached_embedding(text)
            )

            if cached_embedding is not None:

                print("Redis cache HIT")

                return cached_embedding

            print("Redis cache MISS")

            async with semaphore:

                embedding = await _embed_via_ollama(
                    text,
                    client,
                )

            await cache_embedding(
                text,
                embedding,
            )

            print("Embedding stored in Redis")

            return embedding

        return await asyncio.gather(
            *(embed_one(text) for text in texts)
        )