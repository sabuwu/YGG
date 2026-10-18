import asyncio
import logging
import os
from pathlib import Path
import sys

import discord
from discord import app_commands
from dotenv import load_dotenv
from prompt_toolkit.patch_stdout import patch_stdout

from ygg.app.ygg_terminal.terminal import Terminal

load_dotenv()

logger = logging.getLogger(__name__)


class App(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.DISCORD_API_KEY = os.getenv("DISCORD_API_KEY")
        self.tree = app_commands.CommandTree(self)
        self.tree.command(name="ping", description="Check whether Ygg is responding.")(
            self.ping
        )

    async def setup_hook(self) -> None:
        try:
            commands = await self.tree.sync()
        except discord.HTTPException:
            logger.exception(
                "Failed to sync / commands. "
                "Message commands remain available."
            )
        else:
            logger.info(f"{len(commands)} / command(s) synced.")

    async def on_ready(self) -> None:
        logger.info(f"Connected to Discord as {self.user}. Use @ygg ping or /ping.")

    async def ping(self, interaction: discord.Interaction) -> None:
        logger.info(f"/ping received from {interaction.user}.")
        await interaction.response.send_message("🏓 pong!")
        logger.info(f"/ping executed by {interaction.user}.")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        print(f"{message.author}: {message.content}")

        parts = (message.content or "").split()
        if len(parts) == 1:
            if parts[0].casefold() != "/ping":
                return
        elif len(parts) == 2:
            prefixes = {"@ygg"}
            if self.user is not None:
                prefixes.update({f"<@{self.user.id}>", f"<@!{self.user.id}>"})

            bot_role = message.guild.self_role if message.guild is not None else None
            if bot_role is not None:
                prefixes.add(bot_role.mention)

            prefix, command = parts
            if prefix.casefold() not in prefixes or command.casefold() != "ping":
                return
        else:
            return

        logger.info(f"Message ping received from {message.author}: {message.content}")
        await message.channel.send("🏓 pong!")
        logger.info(f"Pong sent to {message.author}.")


async def run_app(app: App, token: str) -> None:
    async with app:
        tasks = [asyncio.create_task(app.start(token), name="discord")]
        if sys.stdin.isatty():
            tasks.append(
                asyncio.create_task(Terminal(app).start_terminal(), name="terminal")
            )
        else:
            logger.info("Non-TTY input; running the bot without an interactive prompt.")

        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in tasks:
                if task in done:
                    task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    app = App()

    if not app.DISCORD_API_KEY:
        raise RuntimeError("DISCORD_API_KEY not found in .env")

    with patch_stdout(raw=True):
        log_directory = Path("logs")
        log_directory.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            filename=str(log_directory / "ygg_logs.log"),
            encoding="utf-8",
            force=True,
        )

        logger.info("Starting Ygg...")
        try:
            asyncio.run(run_app(app, app.DISCORD_API_KEY))
        except discord.PrivilegedIntentsRequired as error:
            raise RuntimeError(
                "Enable Message Content Intent in Discord Developer Portal > "
                "Bot > Privileged Gateway Intents, then restart Ygg."
            ) from error
        except KeyboardInterrupt:
            print("Goodbye!")
