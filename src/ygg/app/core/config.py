"""Load credentials only when the application starts."""

import os

from dotenv import load_dotenv


def load_token() -> str:
    load_dotenv()
    token = os.getenv("DISCORD_API_KEY")
    if not token:
        raise RuntimeError("DISCORD_API_KEY not found in .env")
    return token
