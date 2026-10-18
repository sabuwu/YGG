import asyncio
import io
import logging
import unittest
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, MagicMock, patch

from ygg.app.ygg_terminal.terminal import Terminal


class TerminalTests(unittest.IsolatedAsyncioTestCase):
    async def run_terminal(self, *responses):
        session = MagicMock()
        session.prompt_async = AsyncMock(side_effect=responses)
        output = io.StringIO()

        with (
            patch(
                "ygg.app.ygg_terminal.terminal.PromptSession", return_value=session
            ),
            redirect_stdout(output),
        ):
            await Terminal().start_terminal()

        return session, output.getvalue()

    async def test_exit_commands_return_normally(self):
        for command in ("stop", "exit", "quit", "bye", "  STOP  ", "\tExIt\n"):
            with self.subTest(command=command):
                session, output = await self.run_terminal(command)

                session.prompt_async.assert_awaited_once_with("YGG > ")
                self.assertIn("Terminal do YGG iniciado.", output)
                self.assertIn("Comandos locais:", output)
                self.assertIn("Encerrando o bot.", output)
                self.assertNotIn("Comando desconhecido", output)

    async def test_help_displays_commands_and_keeps_terminal_open(self):
        for command in ("ajuda", "help", "  AJUDA  "):
            with self.subTest(command=command):
                session, output = await self.run_terminal(command, "exit")

                self.assertEqual(session.prompt_async.await_count, 2)
                self.assertEqual(output.count("Comandos locais:"), 2)
                self.assertNotIn("Comando desconhecido", output)

    async def test_empty_input_keeps_terminal_open(self):
        session, output = await self.run_terminal("", " \t ", "exit")

        self.assertEqual(session.prompt_async.await_count, 3)
        self.assertNotIn("Comando desconhecido", output)

    async def test_clear_logs_clears_screen_and_disables_logging(self):
        with patch("ygg.app.ygg_terminal.terminal.logging.disable") as disable_logging:
            session, output = await self.run_terminal("limpar logs", "exit")

        self.assertEqual(session.prompt_async.await_count, 2)
        self.assertIn("\x1b[2J\x1b[H", output)
        self.assertIn("Tela limpa; logs desabilitados.", output)
        disable_logging.assert_called_once_with(logging.CRITICAL)

    async def test_activate_logs_reenables_logging(self):
        with patch("ygg.app.ygg_terminal.terminal.logging.disable") as disable_logging:
            session, output = await self.run_terminal("ativar logs", "exit")

        self.assertEqual(session.prompt_async.await_count, 2)
        self.assertIn("Logs habilitados.", output)
        disable_logging.assert_called_once_with(logging.NOTSET)

    async def test_unknown_command_displays_guidance_and_keeps_terminal_open(self):
        session, output = await self.run_terminal("inexistente", "exit")

        self.assertEqual(session.prompt_async.await_count, 2)
        self.assertIn("Comando desconhecido: 'inexistente'.", output)
        self.assertIn("Digite ajuda", output)

    async def test_eof_returns_without_retrying_input(self):
        session, output = await self.run_terminal(EOFError())

        session.prompt_async.assert_awaited_once()
        self.assertIn("Encerrando o bot.", output)

    async def test_keyboard_interrupt_returns_without_retrying_input(self):
        session, output = await self.run_terminal(KeyboardInterrupt())

        session.prompt_async.assert_awaited_once()
        self.assertIn("Encerrando o bot.", output)

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
