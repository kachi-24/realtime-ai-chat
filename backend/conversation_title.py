import re


def generate_conversation_title(message: str) -> str:
    """
    Generate a short conversation title from the first user message.
    """

    message = message.strip()

    if not message:
        return "New Conversation"

    # Remove excessive whitespace
    message = re.sub(r"\s+", " ", message)

    # Remove common question punctuation
    message = message.rstrip("?.!")

    # Limit title length
    max_length = 60

    if len(message) <= max_length:
        return message

    shortened = message[:max_length]

    # Avoid cutting a word in half
    shortened = shortened.rsplit(" ", 1)[0]

    return shortened + "..."