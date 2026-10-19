"""All Discord application and message commands."""

import logging

import discord
from discord import app_commands

from ygg.app.moderation.moderation import ban_user

logger = logging.getLogger(__name__)


class DiscordCommands:
    def __init__(self, client: discord.Client) -> None:
        self.client = client

    def register(self, tree: app_commands.CommandTree) -> None:
        tree.command(name="ping", description="Check whether Ygg is responding.")(
            self.ping
        )
        tree.command(
            name="ban", description="Ban a member from this server."
        )(
            self.ban
        )

    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "this commando can only be used in a server.",
                ephemeral=True,
            )

            return

        await interaction.response.defer()
        try:
            await ban_user(interaction.guild, member, reason)
        except discord.HTTPException as error:
            logger.exception("Failed to ban %s from %s.", member, interaction.guild)
            await interaction.followup.send(
                f"Discord could not ban {member}: {error}"
            )
            return

        await interaction.followup.send(f"{member} was banned.")

    async def ping(self, interaction: discord.Interaction) -> None:
        logger.info("/ping received from %s.", interaction.user)
        try:
            await interaction.response.send_message("🏓 pong!")
        except discord.NotFound:
            logger.warning("Could not respond to /ping: interaction is no longer valid.")

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
