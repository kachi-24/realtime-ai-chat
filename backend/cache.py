import hashlib
import json
from redis_client import redis_client

EMBEDDING_CACHE_TTL = 60 * 60 * 24
RETRIEVAL_CACHE_TTL = 60 * 5

# --- Embedding Cache Helpers ---

def embedding_cache_key(text: str) -> str:
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"embedding:nomic-embed-text:{text_hash}"

async def get_cached_embedding(text: str):
    key = embedding_cache_key(text)
    cached = await redis_client.get(key)
    if cached is None:
        return None
    return json.loads(cached)

async def cache_embedding(text: str, embedding: list[float]):
    key = embedding_cache_key(text)
    await redis_client.set(
        key,
        json.dumps(embedding),
        ex=EMBEDDING_CACHE_TTL,
    )

# --- Retrieval Cache Helpers (User Isolated) ---

def retrieval_cache_key(
    user_id: str,
    query: str,
    top_k: int,
) -> str:
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return (
        f"retrieval:"
        f"user:{user_id}:"
        f"{query_hash}:"
        f"top_k:{top_k}"
    )

async def get_cached_retrieval(
    user_id: str,
    query: str,
    top_k: int = 5,
):
    key = retrieval_cache_key(
        user_id,
        query,
        top_k,
    )
    cached = await redis_client.get(key)
    if cached is None:
        return None
    return json.loads(cached)

async def cache_retrieval(
    user_id: str,
    query: str,
    results: list,
    top_k: int = 5,
):
    key = retrieval_cache_key(
        user_id,
        query,
        top_k,
    )
    await redis_client.set(
        key,
        json.dumps(results),
        ex=RETRIEVAL_CACHE_TTL,
    )