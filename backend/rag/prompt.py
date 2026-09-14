# --------------------------------------------------------
# Cosine distance ranges from 0 (identical) to 2 (opposite).
# Chunks with a distance above this threshold are treated
# as "not actually relevant" to the question and excluded
# from the prompt entirely. Tune this if you find it's
# too strict (missing real matches) or too loose (still
# pulling in unrelated chunks).
# --------------------------------------------------------

RELEVANCE_DISTANCE_THRESHOLD = 0.5


def build_rag_prompt(
    question: str,
    history: list,
    retrieved_chunks: list,
) -> str:

    # -----------------------------------------
    # Only keep chunks that are actually close
    # enough to the question to be relevant.
    # Irrelevant chunks are dropped instead of
    # being injected into the prompt anyway.
    # -----------------------------------------

    relevant_chunks = [
        (chunk, distance, filename)
        for chunk, distance, filename in retrieved_chunks
        if distance <= RELEVANCE_DISTANCE_THRESHOLD
    ]

    context_parts = []

    for index, (chunk, distance, filename) in enumerate(
        relevant_chunks,
        start=1,
    ):
        context_parts.append(
            f"""
[Context {index} — from: {filename}]
Document chunk:
{chunk.content}
"""
        )

    context = "\n".join(context_parts)

    history_parts = []

    for message in history:

        if message.role == "user":
            history_parts.append(
                f"User: {message.content}"
            )

        elif message.role == "assistant":
            history_parts.append(
                f"Assistant: {message.content}"
            )

    conversation_history = "\n".join(
        history_parts
    )

    # -----------------------------------------
    # If nothing relevant was retrieved, don't
    # mention documents at all — just answer the
    # question normally, like a regular chat.
    # -----------------------------------------

    if not relevant_chunks:

        prompt = f"""
You are a helpful AI assistant.

Answer the user's question directly and naturally.
The user has uploaded documents, but nothing in
them appears relevant to this particular question,
so do not mention the documents or say anything
about what they do or do not contain. Just answer
the question as you normally would.

CONVERSATION HISTORY:

{conversation_history}

CURRENT USER QUESTION:

{question}

ANSWER:
"""

        return prompt

    # -----------------------------------------
    # Otherwise, relevant context was found —
    # use it, but the model is still free to
    # answer questions outside that context.
    # -----------------------------------------

    prompt = f"""
You are a helpful AI assistant.

You have access to information retrieved from
the user's documents, shown below. This context
was retrieved because it appeared relevant to the
current question.

Use ONLY the information contained in the provided
context to answer questions about the user's
documents. Do not claim that information came from
the documents if it was not present in the
retrieved context. Do not invent facts.

If the current question is unrelated to the
retrieved context, ignore the context and just
answer the question normally — do not say that
the documents lack information for a question
that was never about the documents in the first
place.

If the context IS relevant but doesn't actually
contain enough detail to answer the question, say
that the answer cannot be found in the provided
documents rather than guessing.

RETRIEVED CONTEXT:

{context}

CONVERSATION HISTORY:

{conversation_history}

CURRENT USER QUESTION:

{question}

ANSWER:
"""

    return prompt