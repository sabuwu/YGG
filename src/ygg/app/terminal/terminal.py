import asyncio

import discord

from .chat import ChannelChat
from .commands import TerminalCommands
from .session import TerminalSession


class Terminal:
    """Coordinate the terminal session and its asynchronous tasks."""

    def __init__(self, client: discord.Client | None = None) -> None:
        self.session: TerminalSession | None = None
        self.chat = ChannelChat(client, self.write)
        self.commands = TerminalCommands(self.chat, self.write)

    def write(self, text: str, *, name_style: tuple[int, str] | None = None) -> None:
        if self.session is not None:
            if name_style is None:
                self.session.write(text)
            else:
                self.session.write(text, name_style=name_style)
        else:
            print(text)

    def on_message(self, message: discord.Message) -> None:
        self.chat.on_message(message)

    async def start_terminal(self) -> None:
        session = TerminalSession()
        self.session = session
        tasks = [
            asyncio.create_task(session.run_async()),
            asyncio.create_task(self.commands.run(session)),
        ]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.session = None
