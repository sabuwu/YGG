"""Application startup shared by the console, module and IDE entry points."""

import asyncio
import logging

import discord
from prompt_toolkit.patch_stdout import patch_stdout

from ygg.app.discord_bot.client import App
from ygg.app.core.config import load_token
from ygg.app.core.logging import configure_logging
from ygg.app.core.runtime import run_app


logger = logging.getLogger(__name__)


def main() -> None:
    token = load_token()
    app = App()

    with patch_stdout(raw=True):
        configure_logging()
        logger.info("Starting Ygg...")
        try:
            asyncio.run(run_app(app, token))
        except discord.PrivilegedIntentsRequired as error:
            raise RuntimeError(
                "Enable Message Content Intent in Discord Developer Portal > "
                "Bot > Privileged Gateway Intents, then restart Ygg."
            ) from error
        except KeyboardInterrupt:
            print("Goodbye!")


if __name__ == "__main__":
    main()
