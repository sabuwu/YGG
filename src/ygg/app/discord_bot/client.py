"""Discord connection, events and forwarding to the terminal or commands."""

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from rich.console import Console
from rich.text import Text

from ygg.app.discord_bot.commands import DiscordCommands

if TYPE_CHECKING:
    from ygg.app.terminal.terminal import Terminal

logger = logging.getLogger(__name__)


class App(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.terminal: Terminal | None = None
        self.tree = app_commands.CommandTree(self)
        self.commands = DiscordCommands(self)
        self.commands.register(self.tree)
        self.console = Console()

    async def setup_hook(self) -> None:
        try:
            commands = await self.tree.sync()
        except discord.HTTPException:
            logger.exception(
                "Failed to sync / commands. "
                "Message commands remain available."
            )
        else:
            logger.info("%s / command(s) synced.", len(commands))

    async def on_ready(self) -> None:
        logger.info("Connected to Discord as %s. Use @ygg ping or /ping.", self.user)

    async def on_message(self, message: discord.Message) -> None:
        if self.terminal is not None:
            self.terminal.on_message(message)

        if message.author.bot:
            return

        if self.terminal is None:
            colour = getattr(message.author, "colour", None)
            style = (
                str(colour)
                if isinstance(colour, discord.Colour) and colour.value
                else ""
            )
            output = Text()
            output.append(str(message.author), style=style)
            output.append(f": {message.content or ''}")
            self.console.print(output)

        await self.commands.handle_message(message)
