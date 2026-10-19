import logging
from collections.abc import Callable

from .chat import ChannelChat
from .session import TerminalSession


class TerminalCommands:
    """Handle local commands, channel selection, and chat navigation."""

    def __init__(self, chat: ChannelChat, write: Callable[..., None]) -> None:
        self.chat = chat
        self.write = write

    async def run(self, session: TerminalSession) -> None:
        help_message = (
            "Local commands: send_message to enter a server and text channel; "
            "exit_channel to return to that server's channel list; "
            "exit_server to return to the server list; "
            "help to show this message; clear logs to clear the screen and disable logging; "
            "enable logs to re-enable logging; stop/exit/quit/bye to shut down the bot."
        )

        self.write("YGG terminal started.")
        self.write(help_message)
        while True:
            try:
                command = (await session.prompt_async(" >>> ")).strip().casefold()
            except (EOFError, KeyboardInterrupt):
                self.write("\nGoodbye!")
                return

            command = command.removeprefix("/")
            match command:
                case _ if command in {"stop", "exit", "quit", "bye"}:
                    if command == "bye":
                        self.write("bye, bye ^~^")
                    self.write("\nGoodbye!")
                    return
                case "help":
                    self.write(help_message)
                case "send_message":
                    try:
                        await self.send_message(session)
                    except (EOFError, KeyboardInterrupt):
                        self.write("\nMessage cancelled.")
                case "clear logs":
                    session.clear()
                    logging.disable(logging.CRITICAL)
                    self.write("Screen cleared; logging disabled.")
                case "enable logs":
                    logging.disable(logging.NOTSET)
                    self.write("Logging enabled.")
                case "":
                    continue
                case _:
                    self.write(f"Unknown command: '{command}'. Type help for guidance.")

    async def send_message(self, session: TerminalSession) -> None:
        client = self.chat.client
        if client is None:
            self.write("No Discord servers are available. Check that the bot is connected.")
            return

        if not client.is_ready():
            self.write("Waiting for the Discord connection...")
            await client.wait_until_ready()

        if not client.guilds:
            self.write("No Discord servers are available. Check that the bot is connected.")
            return

        while True:
            self.write("Available servers:")
            for guild in client.guilds:
                self.write(f" - {guild.name}")

            server = (await session.prompt_async("Server: ")).strip()
            guild = next(
                (
                    item
                    for item in client.guilds
                    if item.name.casefold() == server.casefold()
                ),
                None,
            )
            if guild is None:
                self.write(f"Server not found: {server!r}.")
                continue

            exit_server = False
            while not exit_server:
                channels = guild.text_channels
                if not channels:
                    self.write(f"No text channels are available in {guild.name!r}.")

                self.write(f"Text channels in {guild.name}:")
                for channel in channels:
                    self.write(f" - {channel.name}")

                channel_name = (await session.prompt_async(f"{guild.name} > ")).strip()
                if channel_name.casefold() == "exit_server":
                    exit_server = True
                    continue

                channel = next(
                    (
                        item
                        for item in channels
                        if item.name.casefold() == channel_name.casefold()
                    ),
                    None,
                )
                if channel is None:
                    self.write(f"Text channel not found: {channel_name!r}.")
                    continue

                self.chat.channel = channel
                try:
                    self.write(f"{guild.name} - {channel.name}")
                    await self.chat.load_history(channel)
                    exit_channel = False
                    while not exit_channel:
                        content = (await session.prompt_async(">>> ")).strip()
                        match content.casefold():
                            case "exit_channel":
                                exit_channel = True
                                continue
                            case "exit_server":
                                exit_server = True
                                exit_channel = True
                                continue
                            case "":
                                continue
                            case _:
                                pass

                        await self.chat.send_message(content)
                finally:
                    self.chat.channel = None
