import discord


async def ban_user(
    guild: discord.Guild,
    user: discord.User,
    reason: str = "",
) -> None:
    await guild.ban(user, reason=reason)