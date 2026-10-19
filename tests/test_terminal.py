import asyncio
import io
import logging
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import discord
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from ygg.app.terminal.chat import ChannelChat
from ygg.app.terminal import commands as commands_module
from ygg.app.terminal.commands import TerminalCommands
from ygg.app.terminal.session import TerminalSession
from ygg.app.terminal.terminal import Terminal


class TerminalTests(unittest.IsolatedAsyncioTestCase):
    async def run_terminal(
        self, *responses: str | BaseException, client: Any = None
    ) -> tuple[MagicMock, str]:
        session = MagicMock()
        session.greet = AsyncMock()
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
                "ygg.app.terminal.terminal.TerminalSession", return_value=session
            ),
            redirect_stdout(output),
        ):
            await Terminal(client).start_terminal()

        return session, output.getvalue()

    async def test_exit_commands_return_normally(self):
        for command in ("stop", "exit", "quit", "bye", "  STOP  ", "\tExIt\n", "/exit"):
            with self.subTest(command=command):
                session, output = await self.run_terminal(command)

                session.prompt_async.assert_awaited_once_with(" >>> ")
                session.greet.assert_awaited_once_with()
                session.hide_welcome.assert_called_once_with()
                self.assertIn("Goodbye!", output)
                self.assertNotIn("Unknown command", output)

    async def test_help_displays_commands_and_keeps_terminal_open(self):
        for command in ("help", "  HELP  ", "/help"):
            with self.subTest(command=command):
                session, output = await self.run_terminal(command, "exit")

                self.assertEqual(session.prompt_async.await_count, 2)
                self.assertEqual(output.count("Local commands:"), 1)
                self.assertNotIn("Unknown command", output)

    async def test_empty_input_keeps_terminal_open(self):
        session, output = await self.run_terminal("", " \t ", "exit")

        self.assertEqual(session.prompt_async.await_count, 3)
        session.hide_welcome.assert_called_once_with()
        self.assertNotIn("Unknown command", output)

    async def test_clear_logs_clears_screen_and_disables_logging(self):
        with patch("ygg.app.terminal.commands.logging.disable") as disable_logging:
            session, output = await self.run_terminal("clear logs", "exit")

        self.assertEqual(session.prompt_async.await_count, 2)
        session.clear.assert_called_once_with()
        self.assertIn("Screen cleared; logging disabled.", output)
        disable_logging.assert_called_once_with(logging.CRITICAL)

    async def test_activate_logs_reenables_logging(self):
        with patch("ygg.app.terminal.commands.logging.disable") as disable_logging:
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
            "chat",
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
        self.assertNotIn("Message sent", output)
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
            "chat", "missing", KeyboardInterrupt(), "exit", client=client
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
            "chat",
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
        channel.send.assert_awaited_once_with("hello from server two")
        self.assertNotIn("Message sent", output)

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
            "chat",
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
        session.greet = AsyncMock()
        session.prompt_async = AsyncMock(side_effect=asyncio.CancelledError())
        session.run_async = AsyncMock(side_effect=asyncio.Event().wait)

        with (
            patch(
                "ygg.app.terminal.terminal.TerminalSession", return_value=session
            ),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await Terminal().start_terminal()

        session.prompt_async.assert_awaited_once()

    async def test_session_and_command_failures_cancel_the_other_task(self):
        for failing_task in ("session", "commands"):
            with self.subTest(failing_task=failing_task):
                pending_started = asyncio.Event()
                pending_finished = asyncio.Event()

                async def pending(*args):
                    pending_started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        pending_finished.set()

                async def fail(*args):
                    await pending_started.wait()
                    raise RuntimeError("terminal failure")

                session = MagicMock()
                session.greet = AsyncMock()
                session.run_async = AsyncMock(
                    side_effect=fail if failing_task == "session" else pending
                )
                session.prompt_async = AsyncMock(
                    side_effect=fail if failing_task == "commands" else pending
                )
                terminal = Terminal()
                with patch(
                    "ygg.app.terminal.terminal.TerminalSession", return_value=session
                ):
                    with self.assertRaisesRegex(RuntimeError, "terminal failure"):
                        await terminal.start_terminal()

                self.assertTrue(pending_finished.is_set())
                self.assertIsNone(terminal.session)


class TerminalCommandsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.channel = MagicMock(name="channel")
        self.channel.name = "general"
        self.channel.send = AsyncMock()

        async def history():
            for message in ():
                yield message

        self.channel.history.return_value = history()
        self.guild = SimpleNamespace(name="server", text_channels=[self.channel])
        self.client = MagicMock()
        self.client.guilds = [self.guild]
        self.write = MagicMock()
        self.chat = ChannelChat(self.client, self.write)
        self.commands = TerminalCommands(self.chat, self.write)

    async def test_send_error_allows_another_message_without_confirming_or_retrying(self):
        error = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "denied")
        self.channel.send.side_effect = [error, None]

        def responses():
            yield "server"
            yield "general"
            yield "failed message"
            self.assertFalse(any(
                args.args[0].startswith("Message sent") for args in self.write.call_args_list
            ))
            yield "successful message"
            yield "exit_channel"
            raise EOFError()

        inputs = responses()
        session = MagicMock()
        session.prompt_async = AsyncMock(side_effect=lambda prompt: next(inputs))
        with self.assertLogs(level="ERROR"), self.assertRaises(EOFError):
            await self.commands.send_message(session)

        self.channel.send.assert_has_awaits([
            call("failed message"), call("successful message")
        ])
        self.assertEqual(self.channel.send.await_count, 2)
        lines = [args.args[0] for args in self.write.call_args_list]
        self.assertTrue(any("HTTP 403" in line for line in lines))
        self.assertFalse(any(line.startswith("Message sent") for line in lines))
        self.assertIsNone(self.chat.channel)

    async def test_navigation_clears_active_channel_before_showing_menus(self):
        for command, menu in (("exit_channel", "server > "), ("exit_server", "Server: ")):
            with self.subTest(command=command):
                async def history():
                    for message in ():
                        yield message

                self.channel.history.return_value = history()
                prompts = iter(["server", "general", command])

                def respond(prompt):
                    if prompt == ">>> ":
                        self.assertIs(self.chat.channel, self.channel)
                    else:
                        self.assertIsNone(self.chat.channel)
                    try:
                        return next(prompts)
                    except StopIteration:
                        self.assertEqual(prompt, menu)
                        raise EOFError()

                session = MagicMock()
                session.prompt_async = AsyncMock(side_effect=respond)
                with self.assertRaises(EOFError):
                    await self.commands.send_message(session)
                self.assertIsNone(self.chat.channel)

    async def test_interrupt_in_channel_returns_to_local_commands(self):
        for error in (EOFError(), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                async def history():
                    for message in ():
                        yield message

                self.channel.history.return_value = history()
                session = MagicMock()
                session.greet = AsyncMock()
                session.prompt_async = AsyncMock(side_effect=[
                    "chat", "server", "general", error, "exit"
                ])
                terminal = Terminal(self.client)
                terminal.session = session

                await terminal.commands.run(session)

                session.write.assert_any_call("\nMessage cancelled.")
                session.write.assert_any_call("\nGoodbye!")
                self.assertIsNone(terminal.chat.channel)

    async def test_ban_command_fetches_user_and_bans_from_selected_server(self):
        user = SimpleNamespace(__str__=lambda self: "test user")
        self.client.fetch_user = AsyncMock(return_value=user)
        session = MagicMock()
        session.greet = AsyncMock()
        session.prompt_async = AsyncMock(
            side_effect=["ban", "server", "123456789", "test reason", "exit"]
        )

        with patch.object(commands_module, "ban_user", AsyncMock()) as ban_user:
            await self.commands.run(session)

        self.client.fetch_user.assert_awaited_once_with(123456789)
        ban_user.assert_awaited_once_with(self.guild, user, "test reason")
        self.write.assert_any_call(f"{user} was banned from {self.guild.name}.")

    async def test_ban_command_can_be_cancelled_without_exiting_terminal(self):
        session = MagicMock()
        session.greet = AsyncMock()
        session.prompt_async = AsyncMock(side_effect=["ban", KeyboardInterrupt(), "exit"])

        await self.commands.run(session)

        self.write.assert_any_call("\nBan cancelled.")
        self.write.assert_any_call("\nGoodbye!")

    async def test_cancellation_during_history_or_input_clears_active_channel(self):
        for stage in ("history", "input"):
            with self.subTest(stage=stage):
                waiting = asyncio.Event()

                async def history():
                    if stage == "history":
                        waiting.set()
                        await asyncio.Event().wait()
                    for message in ():
                        yield message

                self.channel.history.return_value = history()
                responses = iter(["server", "general"])

                async def respond(prompt):
                    if prompt == ">>> ":
                        waiting.set()
                        await asyncio.Event().wait()
                    return next(responses)

                session = MagicMock()
                session.prompt_async = AsyncMock(side_effect=respond)
                task = asyncio.create_task(self.commands.send_message(session))
                try:
                    await asyncio.wait_for(waiting.wait(), 1)
                    self.assertIs(self.chat.channel, self.channel)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    self.assertIsNone(self.chat.channel)
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)


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
        terminal.chat.channel = channel
        terminal.session = MagicMock()
        await terminal.chat.load_history(channel)
        terminal.on_message(message)
        self.assertEqual(terminal.session.write.call_args_list, [
            call("Nickname: hello\nsecond line", name_style=(8, "fg:#12ab34")),
            call("Nickname: hello\nsecond line", name_style=(8, "fg:#12ab34")),
        ])

        message.author.colour = discord.Colour.default()
        terminal.chat.write_message(message)
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
        await terminal.chat.load_history(channel)

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
            await terminal.chat.load_history(channel)
        self.assertIn("Read Message History", terminal.session.write.call_args.args[0])

    async def test_live_messages_only_display_for_active_channel_including_bots(self):
        terminal = Terminal()
        terminal.session = MagicMock()
        terminal.chat.channel = SimpleNamespace(id=1)
        message = SimpleNamespace(
            author="bot", content="pong", attachments=[], channel=SimpleNamespace(id=2)
        )
        terminal.on_message(message)
        terminal.session.write.assert_not_called()
        message.channel.id = 1
        terminal.on_message(message)
        terminal.session.write.assert_called_once_with("bot: pong")


class LayoutTests(unittest.IsolatedAsyncioTestCase):
    def rendered_text(self, session: TerminalSession) -> str:
        screen = session.app.renderer._last_screen
        return "\n".join(
            "".join(character.char for _, character in sorted(row.items()))
            for _, row in sorted(screen.data_buffer.items())
        )

    async def test_welcome_asks_name_and_remains_until_first_nonempty_command(self):
        local_now = datetime(
            2026, 10, 19, 9, 23, 45, 123456,
            tzinfo=timezone(timedelta(hours=-3)),
        )
        with (
            create_pipe_input() as pipe,
            patch("ygg.app.terminal.session.datetime") as clock,
        ):
            clock.now.return_value.astimezone.return_value = local_now
            session = TerminalSession(input=pipe, output=DummyOutput())
            commands = TerminalCommands(ChannelChat(None, session.write), session.write)
            runner = asyncio.create_task(session.run_async())
            command_task = asyncio.create_task(commands.run(session))
            try:
                await asyncio.sleep(0.05)
                self.assertIn("__  ______", self.rendered_text(session))
                self.assertEqual(session.prompt, "enter your name: ")
                clock.now.assert_not_called()

                pipe.send_text("   \r")
                await asyncio.sleep(0.05)
                self.assertEqual(session.prompt, "enter your name: ")
                self.assertEqual(session.greeting_text, "")
                clock.now.assert_not_called()

                pipe.send_text("  Ada  ")
                await asyncio.sleep(0.05)
                clock.now.assert_not_called()
                pipe.send_text("\r")
                await asyncio.sleep(0.05)
                greeting = "> hello Ada! 2026-10-19 09:23:45-03:00"
                self.assertEqual(session.greeting_text, greeting)
                clock.now.assert_called_once_with()
                clock.now.return_value.astimezone.assert_called_once_with()
                self.assertEqual(session.prompt, " >>> ")
                self.assertTrue(session.welcome_visible)
                self.assertIn(greeting, self.rendered_text(session))

                for blank_command in ("   ", "/"):
                    pipe.send_text(blank_command + "\r")
                    await asyncio.sleep(0.05)
                    self.assertTrue(session.welcome_visible)
                    self.assertIn("__  ______", self.rendered_text(session))

                pipe.send_text("help")
                await asyncio.sleep(0.05)
                self.assertTrue(session.welcome_visible)
                self.assertIn(greeting, self.rendered_text(session))
                pipe.send_text("\r")
                await asyncio.sleep(0.05)
                self.assertFalse(session.welcome_visible)
                self.assertIn("Local commands:", session.output.text)
                self.assertNotIn("__  ______", self.rendered_text(session))
                self.assertNotIn(greeting, self.rendered_text(session))

                session.clear()
                await asyncio.sleep(0.05)
                self.assertFalse(session.welcome_visible)
                self.assertEqual(session.output.text, "")
                self.assertNotIn("__  ______", self.rendered_text(session))
                self.assertNotIn(greeting, self.rendered_text(session))
                pipe.send_text("exit\r")
                await asyncio.wait_for(command_task, 1)
            finally:
                command_task.cancel()
                runner.cancel()
                await asyncio.gather(command_task, runner, return_exceptions=True)

    async def test_interrupt_or_eof_during_name_input_exits_without_commands(self):
        for key in ("\x03", "\x04"):
            with self.subTest(key=repr(key)), create_pipe_input() as pipe:
                session = TerminalSession(input=pipe, output=DummyOutput())
                commands = TerminalCommands(ChannelChat(None, session.write), session.write)
                runner = asyncio.create_task(session.run_async())
                command_task = asyncio.create_task(commands.run(session))
                try:
                    await asyncio.sleep(0.05)
                    pipe.send_text(key)
                    await asyncio.wait_for(command_task, 1)
                    self.assertIn("Goodbye!", session.output.text)
                    self.assertEqual(session.prompt, "enter your name: ")
                    self.assertEqual(session.greeting_text, "")
                    self.assertTrue(session.welcome_visible)
                    self.assertIsNone(session.pending)
                finally:
                    command_task.cancel()
                    runner.cancel()
                    await asyncio.gather(command_task, runner, return_exceptions=True)

    async def test_cancellation_during_name_input_propagates_and_releases_prompt(self):
        with create_pipe_input() as pipe:
            session = TerminalSession(input=pipe, output=DummyOutput())
            commands = TerminalCommands(ChannelChat(None, session.write), session.write)
            command_task = asyncio.create_task(commands.run(session))
            try:
                await asyncio.sleep(0)
                self.assertIsNotNone(session.pending)
                command_task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await command_task
                self.assertIsNone(session.pending)
                self.assertEqual(session.greeting_text, "")
                self.assertNotIn("Goodbye!", session.output.text)
                self.assertTrue(session.welcome_visible)
            finally:
                command_task.cancel()
                await asyncio.gather(command_task, return_exceptions=True)

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
