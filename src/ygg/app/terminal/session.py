import asyncio

from prompt_toolkit.application import Application
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.widgets import TextArea


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
