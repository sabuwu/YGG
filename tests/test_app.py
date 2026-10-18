import asyncio
import importlib
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

TEST_TOKEN = "test-discord-token"
with patch("dotenv.load_dotenv"), patch.dict(
    os.environ, {"DISCORD_API_KEY": TEST_TOKEN}, clear=True
):
    app_module = importlib.import_module("ygg.app.app")


class AppCommandsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with patch.dict(os.environ, {"DISCORD_API_KEY": TEST_TOKEN}, clear=True):
            self.app = app_module.App()
        self.app._connection.user = SimpleNamespace(id=123456789)

    async def asyncTearDown(self):
        await self.app.close()

    def message(self, content, *, bot=False):
        return SimpleNamespace(
            content=content,
            author=SimpleNamespace(bot=bot),
            channel=SimpleNamespace(send=AsyncMock()),
        )

    async def test_ping_accepts_text_prefix_and_mentions_with_whitespace_and_case(self):
        for content in (
            "@ygg ping",
            "  @YGG   PiNg  ",
            "\t@yGg\npING\t",
            "<@123456789> ping",
            "  <@123456789>\tPING  ",
            "<@!123456789> ping",
            "\n<@!123456789>\tPiNg\n",
        ):
            with self.subTest(content=content):
                message = self.message(content)
                await self.app.on_message(message)
                message.channel.send.assert_awaited_once_with("🏓 pong!")

    async def test_ping_ignores_bots_other_mentions_and_unrelated_messages(self):
        for content, bot in (
            ("@ygg ping", True),
            ("<@123456789> ping", True),
            ("<@987654321> ping", False),
            ("<@!987654321> ping", False),
            ("@yggish ping", False),
            ("hello @ygg ping", False),
            ("@ygg ping extra", False),
            ("@ygg unknown", False),
            ("@yggping", False),
            ("ping", False),
            ("hello", False),
            ("", False),
            (None, False),
        ):
            with self.subTest(content=content, bot=bot):
                message = self.message(content, bot=bot)
                await self.app.on_message(message)
                message.channel.send.assert_not_awaited()

    async def test_text_prefix_works_before_discord_user_is_available(self):
        self.app._connection.user = None
        message = self.message("@ygg ping")
        await self.app.on_message(message)
        message.channel.send.assert_awaited_once_with("🏓 pong!")

    async def test_slash_ping_is_registered_and_responds(self):
        command = self.app.tree.get_command("ping")
        self.assertIsNotNone(command)
        interaction = SimpleNamespace(
            response=SimpleNamespace(send_message=AsyncMock()),
            user=SimpleNamespace(id=456),
        )

        self.assertIs(command.binding, self.app)
        await command.callback(command.binding, interaction)

        interaction.response.send_message.assert_awaited_once_with("🏓 pong!")

    async def test_setup_hook_syncs_after_ping_is_registered(self):
        async def sync_registered_commands():
            command = self.app.tree.get_command("ping")
            self.assertIsNotNone(command)
            return [command]

        with patch.object(
            self.app.tree, "sync", AsyncMock(side_effect=sync_registered_commands)
        ) as sync:
            await self.app.setup_hook()

        sync.assert_awaited_once_with()

    async def test_sync_http_failure_does_not_prevent_message_commands(self):
        response = SimpleNamespace(status=500, reason="Server Error")
        error = app_module.discord.HTTPException(response, "sync failed")
        with patch.object(self.app.tree, "sync", AsyncMock(side_effect=error)), (
            self.assertLogs(app_module.logger, level="ERROR")
        ):
            await self.app.setup_hook()

        self.assertIsNotNone(self.app.tree.get_command("ping"))
        message = self.message("@ygg ping")
        await self.app.on_message(message)
        message.channel.send.assert_awaited_once_with("🏓 pong!")


class FakeApp:
    def __init__(self, start):
        self.start = AsyncMock(side_effect=start)
        self.close = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.close()


class RunAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_terminal_and_bot_share_loop_and_terminal_exit_cancels_bot(self):
        bot_started = asyncio.Event()
        bot_cancelled = asyncio.Event()
        loops = []

        async def start_bot(token):
            loops.append(asyncio.get_running_loop())
            bot_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                bot_cancelled.set()
                raise

        async def start_terminal():
            loops.append(asyncio.get_running_loop())
            await bot_started.wait()

        app = FakeApp(start_bot)
        terminal = SimpleNamespace(start_terminal=AsyncMock(side_effect=start_terminal))
        stdin = SimpleNamespace(isatty=Mock(return_value=True))
        with patch.object(app_module.sys, "stdin", stdin), patch.object(
            app_module, "Terminal", return_value=terminal
        ):
            await asyncio.wait_for(app_module.run_app(app, TEST_TOKEN), timeout=1)

        app.start.assert_awaited_once_with(TEST_TOKEN)
        terminal.start_terminal.assert_awaited_once_with()
        self.assertEqual(loops, [asyncio.get_running_loop()] * 2)
        self.assertTrue(bot_cancelled.is_set())
        app.close.assert_awaited_once_with()

    async def test_bot_failure_cancels_terminal_and_closes_app(self):
        terminal_started = asyncio.Event()
        terminal_cancelled = asyncio.Event()

        async def start_bot(token):
            await terminal_started.wait()
            raise RuntimeError("bot startup failed")

        async def start_terminal():
            terminal_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                terminal_cancelled.set()
                raise

        app = FakeApp(start_bot)
        terminal = SimpleNamespace(start_terminal=AsyncMock(side_effect=start_terminal))
        stdin = SimpleNamespace(isatty=Mock(return_value=True))
        with patch.object(app_module.sys, "stdin", stdin), patch.object(
            app_module, "Terminal", return_value=terminal
        ):
            with self.assertRaisesRegex(RuntimeError, "bot startup failed"):
                await asyncio.wait_for(app_module.run_app(app, TEST_TOKEN), timeout=1)

        self.assertTrue(terminal_cancelled.is_set())
        app.close.assert_awaited_once_with()

    async def test_without_tty_bot_keeps_running_without_creating_terminal(self):
        bot_started = asyncio.Event()
        finish_bot = asyncio.Event()

        async def start_bot(token):
            bot_started.set()
            await finish_bot.wait()

        app = FakeApp(start_bot)
        stdin = SimpleNamespace(isatty=Mock(return_value=False))
        with patch.object(app_module.sys, "stdin", stdin), patch.object(
            app_module, "Terminal"
        ) as terminal_factory:
            runner = asyncio.create_task(app_module.run_app(app, TEST_TOKEN))
            try:
                await asyncio.wait_for(bot_started.wait(), timeout=1)
                self.assertFalse(runner.done())
                terminal_factory.assert_not_called()
                finish_bot.set()
                await asyncio.wait_for(runner, timeout=1)
            finally:
                runner.cancel()
                await asyncio.gather(runner, return_exceptions=True)

        app.start.assert_awaited_once_with(TEST_TOKEN)
        app.close.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
