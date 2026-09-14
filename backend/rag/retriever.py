from sqlalchemy import select

from models import Document
from models import DocumentChunk


async def retrieve_chunks(
    session,
    query_embedding,
    user_id,
    top_k=5,
):

    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding
    )

    result = await session.execute(
        select(
            DocumentChunk,
            distance.label("distance"),
            Document.filename,
        )
        .join(
            Document,
            DocumentChunk.document_id == Document.id,
        )
        .where(
            Document.user_id == user_id,
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(top_k)
    )

    # Each row is (DocumentChunk, distance, filename)
    return result.all()