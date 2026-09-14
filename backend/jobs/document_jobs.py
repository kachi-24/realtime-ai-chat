import asyncio
import os
from pathlib import Path, PureWindowsPath

import sentry_sdk
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

# ---------------------------------------------------------
# Database models
# ---------------------------------------------------------

from models import (
    Document,
    DocumentChunk,
)

# ---------------------------------------------------------
# RAG modules
# ---------------------------------------------------------

from rag.loader import load_document
from rag.chunker import chunk_text
from rag.embeddings import create_embedding


# ---------------------------------------------------------
# Database configuration
# ---------------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
)


# ---------------------------------------------------------
# Document processing
# ---------------------------------------------------------

async def process_document(
    document_id: str,
    file_path: str,
):
    """
    Process a document in the background.

    Steps:
    1. Load document
    2. Extract text
    3. Create chunks
    4. Generate embeddings
    5. Store chunks in PostgreSQL

    If any step fails, the document's status is set to
    "failed" with the error message recorded.
    """

    print(
        f"Starting document processing: {document_id}"
    )

    # -----------------------------------------------------
    # Sentry context
    # -----------------------------------------------------

    sentry_sdk.set_tag(
        "document_id",
        str(document_id),
    )

    sentry_sdk.set_context(
        "document_processing",
        {
            "document_id": str(document_id),
            "original_file_path": str(file_path),
        },
    )

    # -----------------------------------------------------
    # Create isolated database engine
    # -----------------------------------------------------

    worker_engine = create_async_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )

    WorkerSessionLocal = async_sessionmaker(
        bind=worker_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        # -------------------------------------------------
        # Normalize file path
        # -------------------------------------------------

        # Extract ONLY the raw filename.
        # This removes Windows host paths such as:
        #
        # C:\Users\user\Documents\...\uploads\file.pdf
        #
        # and converts it to:
        #
        # file.pdf
        #
        raw_filename = PureWindowsPath(file_path).name

        path = Path("/app/uploads") / raw_filename

        print(
            f"Targeting normalized container file path: {path}"
        )

        # Add useful Sentry information about the actual
        # container path being accessed.
        sentry_sdk.set_context(
            "document_file",
            {
                "filename": raw_filename,
                "container_path": str(path),
                "file_exists": path.exists(),
            },
        )

        if not path.exists():
            raise FileNotFoundError(
                "Document file does not exist inside container at: "
                f"{path}"
            )

        # -------------------------------------------------
        # 1. Extract text
        # -------------------------------------------------

        text = load_document(
            str(path)
        )

        if not text.strip():
            raise ValueError(
                "No readable text found in document"
            )

        print(
            f"Extracted {len(text)} characters"
        )

        # Update Sentry context with extraction information.
        sentry_sdk.set_context(
            "document_extraction",
            {
                "characters_extracted": len(text),
            },
        )

        # -------------------------------------------------
        # 2. Chunk document
        # -------------------------------------------------

        chunks = chunk_text(
            text,
            chunk_size=300,
            overlap=50,
        )

        print(
            f"Created {len(chunks)} chunks"
        )

        sentry_sdk.set_context(
            "document_chunks",
            {
                "chunk_count": len(chunks),
                "chunk_size": 300,
                "chunk_overlap": 50,
            },
        )

        # -------------------------------------------------
        # 3. Generate embeddings
        # -------------------------------------------------

        embeddings = []

        for index, chunk in enumerate(chunks):
            print(
                f"Embedding chunk "
                f"{index + 1}/{len(chunks)}"
            )

            # Track which chunk is being processed.
            sentry_sdk.set_tag(
                "current_chunk",
                str(index + 1),
            )

            embedding = await create_embedding(
                chunk
            )

            embeddings.append(
                embedding
            )

        # -------------------------------------------------
        # 4. Save to PostgreSQL
        # -------------------------------------------------

        async with WorkerSessionLocal() as session:

            result = await session.execute(
                select(Document)
                .where(
                    Document.id == document_id
                )
            )

            document = (
                result.scalar_one_or_none()
            )

            if document is None:
                raise ValueError(
                    "Document not found"
                )

            for index, (
                chunk,
                embedding,
            ) in enumerate(
                zip(chunks, embeddings)
            ):
                document_chunk = DocumentChunk(
                    document_id=document.id,
                    content=chunk,
                    chunk_index=index,
                    embedding=embedding,
                )

                session.add(
                    document_chunk
                )

            # -------------------------------------------------
            # 5. Mark document as ready
            # -------------------------------------------------

            document.status = "ready"
            document.error_message = None

            await session.commit()

        print(
            f"Document processing complete: "
            f"{document_id}"
        )

        return {
            "document_id": document_id,
            "chunks_created": len(chunks),
        }

    except Exception as error:

        # -------------------------------------------------
        # Sentry error reporting
        # -------------------------------------------------

        print(
            f"Document processing failed: {error}"
        )

        sentry_sdk.set_context(
            "document_error",
            {
                "document_id": str(document_id),
                "file_path": str(file_path),
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )

        sentry_sdk.capture_exception(error)

        # -------------------------------------------------
        # Update document status
        # -------------------------------------------------

        try:
            async with WorkerSessionLocal() as session:

                result = await session.execute(
                    select(Document)
                    .where(
                        Document.id == document_id
                    )
                )

                document = (
                    result.scalar_one_or_none()
                )

                if document:
                    document.status = "failed"

                    document.error_message = (
                        str(error)
                    )

                    await session.commit()

        except Exception as database_error:

            # If updating the document status itself
            # fails, report that failure separately.
            sentry_sdk.capture_exception(
                database_error
            )

            print(
                "Failed to update document status: "
                f"{database_error}"
            )

        # Re-raise the original error so RQ knows that
        # the job failed.
        raise

    finally:

        # -------------------------------------------------
        # Clean up database connections
        # -------------------------------------------------

        await worker_engine.dispose()


# ---------------------------------------------------------
# Synchronous RQ wrapper
# ---------------------------------------------------------

def process_document_sync(
    document_id: str,
    file_path: str,
):
    """
    RQ requires a normal synchronous callable.

    This wrapper runs our async document processing
    function.
    """

    return asyncio.run(
        process_document(
            document_id,
            file_path,
        )
    )