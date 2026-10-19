"""All Discord application and message commands."""

import logging

import discord
from discord import app_commands


logger = logging.getLogger(__name__)


class DiscordCommands:
    def __init__(self, client: discord.Client) -> None:
        self.client = client

    def register(self, tree: app_commands.CommandTree) -> None:
        tree.command(name="ping", description="Check whether Ygg is responding.")(
            self.ping
        )

    async def ping(self, interaction: discord.Interaction) -> None:
        logger.info("/ping received from %s.", interaction.user)
        await interaction.response.send_message("🏓 pong!")
        logger.info("/ping executed by %s.", interaction.user)

    async def handle_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        parts = (message.content or "").split()

        if len(parts) == 1:
            if parts[0].casefold() != "/ping":
                return
        elif len(parts) == 2:
            prefixes = {"@ygg"}
            if self.client.user is not None:
                prefixes.update(
                    {f"<@{self.client.user.id}>", f"<@!{self.client.user.id}>"}
                )

            bot_role = message.guild.self_role if message.guild is not None else None
            if bot_role is not None:
                prefixes.add(bot_role.mention)

            prefix, command = parts
            if prefix.casefold() not in {item.casefold() for item in prefixes}:
                return
            if command.casefold() != "ping":
                return
        else:
            return

        logger.info("Text ping received from %s.", message.author)
        await message.channel.send("🏓 pong!")
        logger.info("Text ping executed by %s.", message.author)
