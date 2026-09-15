import os
from pathlib import Path

from dotenv import load_dotenv

# Same reasoning as database.py / redis_client.py / etc: resolve
# .env relative to this file's location, not the process's
# working directory, so this works the same whether run locally
# or from inside the backend container.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def is_auto_conversation_title_enabled() -> bool:
    return os.getenv(
        "ENABLE_AUTO_CONVERSATION_TITLES",
        "false",
    ).lower() == "true"