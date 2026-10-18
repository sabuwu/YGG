import asyncio
import io
import logging
import unittest
from contextlib import redirect_stdout
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from ygg.app.ygg_terminal.terminal import Terminal


class TerminalTests(unittest.IsolatedAsyncioTestCase):
    async def run_terminal(
        self, *responses: str | BaseException, client: Any = None
    ) -> tuple[MagicMock, str]:
        session = MagicMock()
        session.prompt_async = AsyncMock(side_effect=responses)
        output = io.StringIO()

        with (
            patch(
                "ygg.app.ygg_terminal.terminal.PromptSession", return_value=session
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
        with (
            patch("ygg.app.ygg_terminal.terminal.logging.disable") as disable_logging,
            patch("ygg.app.ygg_terminal.terminal.os.system") as system,
        ):
            session, output = await self.run_terminal("clear logs", "exit")

        self.assertEqual(session.prompt_async.await_count, 2)
        self.assertEqual(system.call_count, 3)
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

        with (
            patch(
                "ygg.app.ygg_terminal.terminal.PromptSession", return_value=session
            ),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await Terminal().start_terminal()

        session.prompt_async.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
