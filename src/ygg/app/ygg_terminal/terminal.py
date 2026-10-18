import logging
import os, sys

from prompt_toolkit import PromptSession
from rich.console import Console
import discord

class Terminal:
    def __init__(self, client: discord.Client | None = None) -> None:
        self.client = client
        self.console = Console()

    async def send_message(self, session: PromptSession[str]) -> None:
        if self.client is None:
            print("No Discord servers are available. Check that the bot is connected.")
            return

        if not self.client.is_ready():
            print("Waiting for the Discord connection...")
            await self.client.wait_until_ready()

        if not self.client.guilds:
            print("No Discord servers are available. Check that the bot is connected.")
            return

        while True:
            print("Available servers:")
            for guild in self.client.guilds:
                print(f" - {guild.name}")

            server = (await session.prompt_async("Server: ")).strip()
            guild = next(
                (
                    item
                    for item in self.client.guilds
                    if item.name.casefold() == server.casefold()
                ),
                None,
            )
            if guild is None:
                print(f"Server not found: {server!r}.")
                continue

            exit_server = False
            while not exit_server:
                channels = guild.text_channels
                if not channels:
                    print(f"No text channels are available in {guild.name!r}.")
                
                sys.stdout.write("\x1b[2J\x1b[H")
                print(f"Text channels in {guild.name}:")
                for channel in channels:
                    print(f" - {channel.name}")

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
                    print(f"Text channel not found: {channel_name!r}.")
                    continue

                exit_channel = False
                status: str | None = None
                while not exit_channel:
                    sys.stdout.write("\x1b[2J\x1b[H")
                    self.console.print(
                        f"{server} - {channel.name}",
                        style="black on white",
                        justify="center",
                        highlight=False,
                    )
                    if status is not None:
                        self.console.print(status)

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

                    try:
                        await channel.send(content)
                    except discord.HTTPException as error:
                        logging.getLogger(__name__).exception(
                            "Failed to send terminal message."
                        )
                        status = (
                            f"Discord returned HTTP {error.status}: {error}. "
                            "Check the bot's channel permissions."
                        )
                        continue

    async def start_terminal(self) -> None:
        session: PromptSession[str] = PromptSession(
            bottom_toolbar=" ",
            reserve_space_for_menu=0,
            erase_when_done=True,
        )
        help_message = (
            "Local commands: send_message to enter a server and text channel; "
            "exit_channel to return to that server's channel list; "
            "exit_server to return to the server list; "
            "help to show this message; clear logs to clear the screen and disable logging; "
            "enable logs to re-enable logging; stop/exit/quit/bye to shut down the bot."
        )

        while True:
            try:
                command = (await session.prompt_async(" >>> ")).strip().casefold()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                return

            command = command.removeprefix("/")
            match command:
                case _ if command in {"stop", "exit", "quit", "bye"}:
                    if command == "bye":
                        print("bye, bye ^~^")
                    print("\nGoodbye!")
                    return
                case "help":
                    print(help_message)
                case "send_message":
                    try:
                        await self.send_message(session)
                    except (EOFError, KeyboardInterrupt):
                        print("\nMessage cancelled.")
                case "clear logs":
                    os.system("cls" if os.name == "nt" else "clear")  # type: ignore
                    logging.disable(logging.CRITICAL)
                    print("Screen cleared; logging disabled.")
                case "enable logs":
                    logging.disable(logging.NOTSET)
                    print("Logging enabled.")
                case "":
                    continue
                case _:
                    print(f"Unknown command: '{command}'. Type help for guidance.")
