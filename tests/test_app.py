import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ygg.app.core import runtime as app_module


TEST_TOKEN = "test-discord-token"


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
        self.assertIsNone(app.terminal)
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
        self.assertIsNone(app.terminal)
        app.close.assert_awaited_once_with()

    async def test_terminal_failure_cancels_bot_and_closes_app(self):
        bot_started = asyncio.Event()
        bot_cancelled = asyncio.Event()

        async def start_bot(token):
            bot_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                bot_cancelled.set()

        async def start_terminal():
            await bot_started.wait()
            raise RuntimeError("terminal failed")

        app = FakeApp(start_bot)
        terminal = SimpleNamespace(start_terminal=AsyncMock(side_effect=start_terminal))
        with patch.object(app_module.sys.stdin, "isatty", return_value=True), (
            patch.object(app_module, "Terminal", return_value=terminal)
        ):
            with self.assertRaisesRegex(RuntimeError, "terminal failed"):
                await asyncio.wait_for(app_module.run_app(app, TEST_TOKEN), timeout=1)

        self.assertTrue(bot_cancelled.is_set())
        self.assertIsNone(app.terminal)
        app.close.assert_awaited_once_with()

    async def test_cancelling_runtime_awaits_both_tasks_and_closes_app(self):
        started = [asyncio.Event(), asyncio.Event()]
        stopped = [asyncio.Event(), asyncio.Event()]

        async def wait_until_cancelled(index):
            started[index].set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped[index].set()

        async def start_terminal():
            await wait_until_cancelled(1)

        async def start_bot(token):
            await wait_until_cancelled(0)

        app = FakeApp(start_bot)
        terminal = SimpleNamespace(start_terminal=AsyncMock(side_effect=start_terminal))
        with patch.object(app_module.sys.stdin, "isatty", return_value=True), (
            patch.object(app_module, "Terminal", return_value=terminal)
        ):
            runner = asyncio.create_task(app_module.run_app(app, TEST_TOKEN))
            try:
                await asyncio.wait_for(
                    asyncio.gather(*(event.wait() for event in started)), timeout=1
                )
                runner.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(runner, timeout=1)
            finally:
                runner.cancel()
                await asyncio.gather(runner, return_exceptions=True)

        self.assertTrue(all(event.is_set() for event in stopped))
        self.assertIsNone(app.terminal)
        app.close.assert_awaited_once_with()

    async def test_terminal_construction_failure_cleans_up_discord_task(self):
        app = FakeApp(None)
        existing_tasks = asyncio.all_tasks()
        with patch.object(app_module.sys.stdin, "isatty", return_value=True), (
            patch.object(app_module, "Terminal", side_effect=RuntimeError("no terminal"))
        ):
            with self.assertRaisesRegex(RuntimeError, "no terminal"):
                await app_module.run_app(app, TEST_TOKEN)

        self.assertEqual(asyncio.all_tasks(), existing_tasks)
        self.assertIsNone(app.terminal)
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
