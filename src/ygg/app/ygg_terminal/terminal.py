import asyncio
import logging

from prompt_toolkit.application import Application
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.widgets import TextArea
import discord


class MessageLexer(Lexer):
    """Style author names without adding escape sequences to selectable text."""

    def __init__(self) -> None:
        self.names: dict[int, tuple[int, str]] = {}

    def lex_document(self, document: Document):
        def get_line(number: int):
            text = document.lines[number]
            length, style = self.names.get(number, (0, ""))
            return [(style, text[:length]), ("", text[length:])]

        return get_line


class TerminalSession:
    """Keep output and input in one application, without clearing on submit."""

    def __init__(self, *, input=None, output=None) -> None:
        self.message_lexer = MessageLexer()
        self.output = TextArea(
            read_only=True, scrollbar=True, wrap_lines=True, lexer=self.message_lexer
        )
        # Keep native terminal selection available until mouse scrolling is requested.
        self.mouse_enabled = False
        self.prompt = ">>> "
        self.pending: asyncio.Future[str] | None = None
        self.input = TextArea(
            height=1,
            multiline=False,
            wrap_lines=False,
            prompt=lambda: self.prompt,
            accept_handler=self._accept,
        )
        bindings = KeyBindings()

        @bindings.add("f2")
        def toggle_mouse(event):
            self.mouse_enabled = not self.mouse_enabled

        @bindings.add("c-c")
        def interrupt(event):
            self._interrupt(KeyboardInterrupt())

        @bindings.add("c-d")
        def eof(event):
            if not self.input.text:
                self._interrupt(EOFError())

        @bindings.add("pageup")
        def page_up(event):
            self.output.buffer.cursor_up(count=max(1, event.app.output.get_size().rows - 3))

        @bindings.add("pagedown")
        def page_down(event):
            self.output.buffer.cursor_down(count=max(1, event.app.output.get_size().rows - 3))

        self.app = Application(
            layout=Layout(
                HSplit([
                    self.output,
                    self.input,
                    Window(
                        height=1,
                        content=FormattedTextControl(
                            lambda: (
                                "Mouse scrolling ON | F2: select/copy text | PgUp/PgDn: scroll"
                                if self.mouse_enabled else
                                "Select/copy text | PgUp/PgDn: scroll | F2: mouse scrolling"
                            )
                        ),
                    ),
                ]),
                focused_element=self.input,
            ),
            key_bindings=bindings,
            full_screen=True,
            mouse_support=Condition(lambda: self.mouse_enabled),
            input=input,
            output=output,
        )

    def _accept(self, buffer) -> bool:
        if self.pending is not None and not self.pending.done():
            self.pending.set_result(buffer.text)
            return False
        return True

    def _interrupt(self, error: BaseException) -> None:
        if self.pending is not None and not self.pending.done():
            self.pending.set_exception(error)
        self.input.buffer.reset()

    async def prompt_async(self, prompt: str) -> str:
        self.prompt = prompt
        self.pending = asyncio.get_running_loop().create_future()
        self.app.invalidate()
        try:
            return await self.pending
        finally:
            self.pending = None

    async def run_async(self) -> None:
        await self.app.run_async()

    def write(self, text: str, *, name_style: tuple[int, str] | None = None) -> None:
        buffer = self.output.buffer
        if name_style is not None:
            self.message_lexer.names[buffer.document.line_count - 1] = name_style
        following = buffer.cursor_position == len(buffer.text)
        content = buffer.text + str(text) + "\n"
        position = len(content) if following else buffer.cursor_position
        buffer.set_document(Document(content, position), bypass_readonly=True)
        self.app.invalidate()

    def clear(self) -> None:
        self.message_lexer.names.clear()
        self.output.buffer.set_document(Document(""), bypass_readonly=True)


class Terminal:
    def __init__(self, client: discord.Client | None = None) -> None:
        self.client = client
        self.session: TerminalSession | None = None
        self.channel: discord.TextChannel | None = None

    def write(self, text: str, *, name_style: tuple[int, str] | None = None) -> None:
        if self.session is not None:
            if name_style is None:
                self.session.write(text)
            else:
                self.session.write(text, name_style=name_style)
        else:
            print(text)

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

    async def send_message(self, session: TerminalSession) -> None:
        if self.client is None:
            self.write("No Discord servers are available. Check that the bot is connected.")
            return

        if not self.client.is_ready():
            self.write("Waiting for the Discord connection...")
            await self.client.wait_until_ready()

        if not self.client.guilds:
            self.write("No Discord servers are available. Check that the bot is connected.")
            return

        while True:
            self.write("Available servers:")
            for guild in self.client.guilds:
                self.write(f" - {guild.name}")

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

                self.channel = channel
                self.write(f"{guild.name} - {channel.name}")
                await self.load_history(channel)
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

                    try:
                        await channel.send(content)
                    except discord.HTTPException as error:
                        logging.getLogger(__name__).exception(
                            "Failed to send terminal message."
                        )
                        self.write(
                            f"Discord returned HTTP {error.status}: {error}. "
                            "Check the bot's channel permissions."
                        )
                        continue
                self.channel = None

    async def start_terminal(self) -> None:
        session = TerminalSession()
        self.session = session
        tasks = [
            asyncio.create_task(session.run_async()),
            asyncio.create_task(self.run_commands(session)),
        ]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.channel = None
            self.session = None

    async def run_commands(self, session: TerminalSession) -> None:
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
                    finally:
                        self.channel = None
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
