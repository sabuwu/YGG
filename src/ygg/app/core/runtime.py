"""Run Discord and the optional terminal on the same event loop."""

import asyncio
import logging
import sys

from ygg.app.discord_bot.client import App
from ygg.app.terminal.terminal import Terminal


logger = logging.getLogger(__name__)


async def run_app(app: App, token: str) -> None:
    async with app:
        tasks = []
        try:
            tasks.append(asyncio.create_task(app.start(token), name="discord"))
            if sys.stdin.isatty():
                app.terminal = Terminal(app)
                tasks.append(
                    asyncio.create_task(app.terminal.start_terminal(), name="terminal")
                )
            else:
                logger.info("Non-TTY input; running the bot without an interactive prompt.")

            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in tasks:
                if task in done:
                    task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            app.terminal = None
