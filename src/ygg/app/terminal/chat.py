import logging
from collections.abc import Callable

import discord


class ChannelChat:
    """Display and send Discord messages for the selected channel."""

    def __init__(
        self, client: discord.Client | None, write: Callable[..., None]
    ) -> None:
        self.client = client
        self.write = write
        self.channel: discord.TextChannel | None = None

    def on_message(self, message: discord.Message) -> None:
        if self.channel is not None and message.channel.id == self.channel.id:
            self.write_message(message)

    def write_message(self, message: discord.Message) -> None:
        name = getattr(message.author, "display_name", str(message.author))
        colour = getattr(message.author, "colour", None)
        if isinstance(colour, discord.Colour) and colour.value:
            self.write(
                self.format_message(message),
                name_style=(len(name), f"fg:{colour}"),
            )
        else:
            self.write(self.format_message(message))

    @staticmethod
    def format_message(message: discord.Message) -> str:
        content = message.content or ""
        attachments = " ".join(attachment.url for attachment in message.attachments)
        name = getattr(message.author, "display_name", str(message.author))
        return f"{name}: {content} {attachments}".rstrip()

    async def load_history(self, channel: discord.TextChannel) -> None:
        try:
            messages = [message async for message in channel.history(limit=100)]
        except discord.HTTPException as error:
            logging.getLogger(__name__).exception("Failed to load channel history.")
            self.write(
                f"Could not load channel history (HTTP {error.status}). "
                "Check View Channel and Read Message History permissions."
            )
            return
        for message in reversed(messages):
            self.write_message(message)

    async def send_message(self, content: str) -> None:
        if self.channel is None:
            return
        try:
            await self.channel.send(content)
        except discord.HTTPException as error:
            logging.getLogger(__name__).exception("Failed to send terminal message.")
            self.write(
                f"Discord returned HTTP {error.status}: {error}. "
                "Check the bot's channel permissions."
            )
