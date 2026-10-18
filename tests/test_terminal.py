import asyncio
import io
import logging
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import discord
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from ygg.app.ygg_terminal.terminal import Terminal, TerminalSession


class TerminalTests(unittest.IsolatedAsyncioTestCase):
    async def run_terminal(
        self, *responses: str | BaseException, client: Any = None
    ) -> tuple[MagicMock, str]:
        session = MagicMock()
        session.prompt_async = AsyncMock(side_effect=responses)
        session.run_async = AsyncMock(side_effect=asyncio.Event().wait)
        session.write.side_effect = print
        if client is not None:
            async def empty_history():
                for message in ():
                    yield message

            for guild in client.guilds:
                for channel in guild.text_channels:
                    channel.history.return_value = empty_history()
        output = io.StringIO()

        with (
            patch(
                "ygg.app.ygg_terminal.terminal.TerminalSession", return_value=session
            ),
            redirect_stdout(output),
        ):
            await Terminal(client).start_terminal()

        return session, output.getvalue()

    async def test_exit_commands_return_normally(self):
        for command in ("stop", "exit", "quit", "bye", "  STOP  ", "\tExIt\n"):
            with self.subTest(command=command):
                session, output = await self.run_terminal(command)

                session.prompt_async.assert_awaited_once_with(" >>> ")
                self.assertIn("YGG terminal started.", output)
                self.assertIn("Local commands:", output)
                self.assertIn("Goodbye!", output)
                self.assertNotIn("Unknown command", output)

    async def test_help_displays_commands_and_keeps_terminal_open(self):
        for command in ("help", "  HELP  "):
            with self.subTest(command=command):
                session, output = await self.run_terminal(command, "exit")

                self.assertEqual(session.prompt_async.await_count, 2)
                self.assertEqual(output.count("Local commands:"), 2)
                self.assertNotIn("Unknown command", output)

    async def test_empty_input_keeps_terminal_open(self):
        session, output = await self.run_terminal("", " \t ", "exit")

        self.assertEqual(session.prompt_async.await_count, 3)
        self.assertNotIn("Unknown command", output)

    async def test_clear_logs_clears_screen_and_disables_logging(self):
        with patch("ygg.app.ygg_terminal.terminal.logging.disable") as disable_logging:
            session, output = await self.run_terminal("clear logs", "exit")

        self.assertEqual(session.prompt_async.await_count, 2)
        session.clear.assert_called_once_with()
        self.assertIn("Screen cleared; logging disabled.", output)
        disable_logging.assert_called_once_with(logging.CRITICAL)

    async def test_activate_logs_reenables_logging(self):
        with patch("ygg.app.ygg_terminal.terminal.logging.disable") as disable_logging:
            session, output = await self.run_terminal("enable logs", "exit")

        self.assertEqual(session.prompt_async.await_count, 2)
        self.assertIn("Logging enabled.", output)
        disable_logging.assert_called_once_with(logging.NOTSET)

    async def test_unknown_command_displays_guidance_and_keeps_terminal_open(self):
        session, output = await self.run_terminal("unknown", "exit")

        self.assertEqual(session.prompt_async.await_count, 2)
        self.assertIn("Unknown command: 'unknown'.", output)
        self.assertIn("Type help", output)

    async def test_send_message_stays_in_channel_until_exit_commands(self):
        chat_channel = MagicMock()
        chat_channel.name = "chat geral"
        chat_channel.send = AsyncMock()
        photos_channel = MagicMock()
        photos_channel.name = "fotos"
        photos_channel.send = AsyncMock()
        voice_channel = MagicMock()
        voice_channel.name = "voz"
        guild = MagicMock()
        guild.name = "Comando Valley"
        guild.text_channels = [chat_channel, photos_channel]
        guild.voice_channels = [voice_channel]
        client = MagicMock()
        client.guilds = [guild]

        session, output = await self.run_terminal(
            "send_message",
            "comando valley",
            "chat geral",
            "hello guys!",
            "another message",
            "exit_channel",
            "fotos",
            "foto enviada",
            "exit_server",
            KeyboardInterrupt(),
            "exit",
            client=client,
        )

        chat_channel.send.assert_has_awaits(
            [call("hello guys!"), call("another message")]
        )
        photos_channel.send.assert_awaited_once_with("foto enviada")
        self.assertIn("Comando Valley", output)
        self.assertIn("chat geral", output)
        self.assertIn("fotos", output)
        self.assertNotIn("voz", output)
        self.assertIn("Message sent to #fotos in Comando Valley.", output)
        self.assertEqual(
            [call.args[0] for call in session.prompt_async.await_args_list],
            [
                " >>> ",
                "Server: ",
                "Comando Valley > ",
                ">>> ",
                ">>> ",
                ">>> ",
                "Comando Valley > ",
                ">>> ",
                ">>> ",
                "Server: ",
                " >>> ",
            ],
        )

    async def test_send_message_reports_missing_server(self):
        guild = MagicMock()
        guild.name = "other server"
        client = MagicMock()
        client.guilds = [guild]

        _, output = await self.run_terminal(
            "send_message", "missing", KeyboardInterrupt(), "exit", client=client
        )

        self.assertIn("Server not found: 'missing'.", output)

    async def test_exit_server_returns_to_server_list(self):
        channel = MagicMock()
        channel.name = "general"
        channel.send = AsyncMock()
        guild = MagicMock()
        guild.name = "server one"
        guild.text_channels = [channel]
        second_guild = MagicMock()
        second_guild.name = "server two"
        second_guild.text_channels = [channel]
        client = MagicMock()
        client.guilds = [guild, second_guild]

        _, output = await self.run_terminal(
            "send_message",
            "server one",
            "exit_server",
            "server two",
            "general",
            "hello from server two",
            "exit_server",
            KeyboardInterrupt(),
            "exit",
            client=client,
        )

        self.assertEqual(output.count("Available servers:"), 3)
        self.assertIn("Message sent to #general in server two.", output)

    async def test_send_message_waits_until_discord_is_ready(self):
        channel = MagicMock()
        channel.name = "general"
        channel.send = AsyncMock()

        async def empty_history():
            for message in ():
                yield message

        channel.history.return_value = empty_history()
        guild = MagicMock()
        guild.name = "server"
        guild.text_channels = [channel]
        client = MagicMock()
        client.is_ready.return_value = False

        async def mark_ready():
            client.guilds = [guild]

        client.wait_until_ready = AsyncMock(side_effect=mark_ready)
        client.guilds = []

        await self.run_terminal(
            "send_message",
            "server",
            "general",
            "hello",
            "exit_server",
            KeyboardInterrupt(),
            "exit",
            client=client,
        )

        client.wait_until_ready.assert_awaited_once_with()
        channel.send.assert_awaited_once_with("hello")

    async def test_eof_returns_without_retrying_input(self):
        session, output = await self.run_terminal(EOFError())

        session.prompt_async.assert_awaited_once()
        self.assertIn("Goodbye!", output)

    async def test_keyboard_interrupt_returns_without_retrying_input(self):
        session, output = await self.run_terminal(KeyboardInterrupt())

        session.prompt_async.assert_awaited_once()
        self.assertIn("Goodbye!", output)

    async def test_cancellation_propagates_without_retrying_input(self):
        session = MagicMock()
        session.prompt_async = AsyncMock(side_effect=asyncio.CancelledError())
        session.run_async = AsyncMock(side_effect=asyncio.Event().wait)

        with (
            patch(
                "ygg.app.ygg_terminal.terminal.TerminalSession", return_value=session
            ),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await Terminal().start_terminal()

        session.prompt_async.assert_awaited_once()


class HistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_role_colour_and_display_name_are_used_in_history_and_live_messages(self):
        message = SimpleNamespace(
            author=SimpleNamespace(display_name="Nickname", colour=discord.Colour(0x12AB34)),
            content="hello\nsecond line",
            attachments=[],
            channel=SimpleNamespace(id=1),
        )

        async def history():
            yield message

        channel = MagicMock(id=1)
        channel.history.return_value = history()
        terminal = Terminal()
        terminal.channel = channel
        terminal.session = MagicMock()
        await terminal.load_history(channel)
        terminal.on_message(message)
        self.assertEqual(terminal.session.write.call_args_list, [
            call("Nickname: hello\nsecond line", name_style=(8, "fg:#12ab34")),
            call("Nickname: hello\nsecond line", name_style=(8, "fg:#12ab34")),
        ])

        message.author.colour = discord.Colour.default()
        terminal.write_message(message)
        terminal.session.write.assert_called_with("Nickname: hello\nsecond line")

    async def test_loads_latest_100_in_chronological_order_with_attachments(self):
        messages = [
            SimpleNamespace(author="user", content=str(number), attachments=[])
            for number in range(100, 0, -1)
        ]
        messages[0].attachments = [SimpleNamespace(url="https://example.com/photo.png")]

        async def history():
            for message in messages:
                yield message

        channel = MagicMock()
        channel.history.return_value = history()
        terminal = Terminal()
        terminal.session = MagicMock()
        await terminal.load_history(channel)

        channel.history.assert_called_once_with(limit=100)
        lines = [args.args[0] for args in terminal.session.write.call_args_list]
        self.assertEqual(len(lines), 100)
        self.assertEqual(lines[0], "user: 1")
        self.assertEqual(lines[-1], "user: 100 https://example.com/photo.png")

    async def test_history_permission_error_keeps_channel_usable(self):
        error = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "denied")
        channel = MagicMock()
        channel.history.side_effect = error
        terminal = Terminal()
        terminal.session = MagicMock()
        with self.assertLogs(level="ERROR"):
            await terminal.load_history(channel)
        self.assertIn("Read Message History", terminal.session.write.call_args.args[0])

    async def test_live_messages_only_display_for_active_channel_including_bots(self):
        terminal = Terminal()
        terminal.session = MagicMock()
        terminal.channel = SimpleNamespace(id=1)
        message = SimpleNamespace(
            author="bot", content="pong", attachments=[], channel=SimpleNamespace(id=2)
        )
        terminal.on_message(message)
        terminal.session.write.assert_not_called()
        message.channel.id = 1
        terminal.on_message(message)
        terminal.session.write.assert_called_once_with("bot: pong")


class LayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_typing_submit_and_resize_preserve_output_and_input_position(self):
        class Output(DummyOutput):
            rows = 12

            def get_size(self):
                return Size(rows=self.rows, columns=60)

        with create_pipe_input() as pipe:
            output = Output()
            session = TerminalSession(input=pipe, output=output)
            self.assertFalse(session.app.mouse_support())
            session.write("history line", name_style=(7, "fg:#12ab34"))
            runner = asyncio.create_task(session.run_async())
            prompt = asyncio.create_task(session.prompt_async(">>> "))
            try:
                await asyncio.sleep(0.05)
                pipe.send_text("hello")
                await asyncio.sleep(0.05)
                self.assertEqual(session.input.text, "hello")
                self.assertEqual(session.output.text, "history line\n")
                screen = session.app.renderer._last_screen
                self.assertEqual(screen.cursor_positions[session.input.window].y, 10)
                self.assertIn("fg:#12ab34", screen.data_buffer[0][0].style)
                self.assertNotIn("fg:#12ab34", screen.data_buffer[0][7].style)

                session.write("new live message")
                self.assertEqual(session.input.text, "hello")
                output.rows = 18
                session.app._on_resize()
                await asyncio.sleep(0.05)
                screen = session.app.renderer._last_screen
                self.assertEqual(screen.cursor_positions[session.input.window].y, 16)

                pipe.send_text("\r")
                self.assertEqual(await asyncio.wait_for(prompt, 1), "hello")
                self.assertEqual(session.input.text, "")
                self.assertEqual(session.output.text, "history line\nnew live message\n")
                self.assertFalse(runner.done())

                session.write("\n".join(f"message {number}" for number in range(100)))
                last_row = session.output.buffer.document.cursor_position_row
                pipe.send_text("\x1b[5~")
                await asyncio.sleep(0.05)
                self.assertLess(session.output.buffer.document.cursor_position_row, last_row)
                self.assertIn("message 0\n", session.output.text)
                self.assertIn("message 99\n", session.output.text)

                position = session.output.buffer.cursor_position
                session.write("incoming while reading history")
                self.assertEqual(session.output.buffer.cursor_position, position)
                await asyncio.sleep(0.05)
                before = session.output.window.render_info.vertical_scroll
                pipe.send_text("\x1bOQ")  # F2: enable mouse scrolling.
                await asyncio.sleep(0.05)
                self.assertTrue(session.app.mouse_support())
                # SGR mouse wheel events over the output pane.
                pipe.send_text("\x1b[<64;5;5M")
                await asyncio.sleep(0.05)
                after = session.output.window.render_info.vertical_scroll
                self.assertLess(after, before)
                self.assertIs(session.app.layout.current_control, session.input.control)
                pipe.send_text("\x1b[<65;5;5M")
                await asyncio.sleep(0.05)
                self.assertGreater(session.output.window.render_info.vertical_scroll, after)

                pipe.send_text("\x1bOQ")  # F2: release mouse for native selection.
                await asyncio.sleep(0.05)
                self.assertFalse(session.app.mouse_support())
                pipe.send_text("\x1bOQ")
                await asyncio.sleep(0.05)
                self.assertTrue(session.app.mouse_support())
                session.clear()
                session.write("plain text")
                fragments = session.message_lexer.lex_document(session.output.buffer.document)(0)
                self.assertEqual(fragments, [("", ""), ("", "plain text")])
            finally:
                prompt.cancel()
                runner.cancel()
                await asyncio.gather(prompt, runner, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
