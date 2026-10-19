"""Discord event and command behavior without a live connection."""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from rich.text import Text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ygg.app.discord_bot import client as client_module
from ygg.app.discord_bot import commands as commands_module


class AppCommandsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = client_module.App()
        self.app.console = Mock()
        self.app._connection.user = SimpleNamespace(id=123456789)

    async def asyncTearDown(self):
        await self.app.close()

    def message(self, content, *, bot=False, guild=None):
        return SimpleNamespace(
            content=content,
            author=SimpleNamespace(bot=bot),
            channel=SimpleNamespace(send=AsyncMock()),
            guild=guild,
        )

    async def test_console_handles_author_without_colour_and_literal_markup(self):
        message = self.message("[bold]literal text[/bold]")
        await self.app.on_message(message)

        self.app.console.print.assert_called_once()
        output = self.app.console.print.call_args.args[0]
        self.assertIsInstance(output, Text)
        self.assertEqual(output.plain, f"{message.author}: [bold]literal text[/bold]")
        self.assertEqual(output.style, "")
        message.channel.send.assert_not_awaited()

    async def test_terminal_receives_bot_messages_before_command_filter(self):
        self.app.terminal = Mock()
        message = self.message("pong", bot=True)
        await self.app.on_message(message)
        self.app.terminal.on_message.assert_called_once_with(message)
        message.channel.send.assert_not_awaited()

    async def test_discord_commands_ignore_bots_when_called_directly(self):
        message = self.message("@ygg ping", bot=True)
        await self.app.commands.handle_message(message)
        message.channel.send.assert_not_awaited()

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
            ("/ping", True),
            ("<@123456789> ping", True),
            ("<@987654321> ping", False),
            ("<@!987654321> ping", False),
            ("@yggish ping", False),
            ("hello @ygg ping", False),
            ("@ygg ping extra", False),
            ("/ping extra", False),
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

    async def test_ping_accepts_plain_slash_text(self):
        for content in ("/ping", "  /PING\n"):
            with self.subTest(content=content):
                message = self.message(content)
                await self.app.on_message(message)
                message.channel.send.assert_awaited_once_with("🏓 pong!")

    async def test_ping_accepts_only_own_managed_role(self):
        guild = SimpleNamespace(self_role=SimpleNamespace(mention="<@&777>"))
        message = self.message("<@&777> ping", guild=guild)
        await self.app.on_message(message)
        message.channel.send.assert_awaited_once_with("🏓 pong!")

        for content in ("<@&888> ping", "<@&777> ping extra", "@everyone ping"):
            with self.subTest(content=content):
                message = self.message(content, guild=guild)
                await self.app.on_message(message)
                message.channel.send.assert_not_awaited()

    async def test_ping_ignores_role_without_own_managed_role(self):
        for guild in (None, SimpleNamespace(self_role=None)):
            with self.subTest(guild=guild):
                message = self.message("<@&777> ping", guild=guild)
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

        self.assertIs(command.binding, self.app.commands)
        await command.callback(command.binding, interaction)

        interaction.response.send_message.assert_awaited_once_with("🏓 pong!")

    async def test_ping_handles_unknown_interaction_without_command_error(self):
        response = SimpleNamespace(status=404, reason="Not Found")
        error = client_module.discord.NotFound(response, "Unknown interaction")
        interaction = SimpleNamespace(
            response=SimpleNamespace(send_message=AsyncMock(side_effect=error)),
            user=SimpleNamespace(id=456),
        )

        with self.assertLogs(commands_module.logger, level="WARNING") as logs:
            await self.app.commands.ping(interaction)

        self.assertIn("interaction is no longer valid", logs.output[0])

    async def test_slash_ban_defers_response_and_reports_success(self):
        guild = SimpleNamespace(name="test server")
        member = SimpleNamespace(__str__=lambda self: "test member")
        interaction = SimpleNamespace(
            guild=guild,
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        with patch.object(commands_module, "ban_user", AsyncMock()) as ban_user:
            await self.app.commands.ban(interaction, member, "test reason")

        interaction.response.defer.assert_awaited_once_with()
        ban_user.assert_awaited_once_with(guild, member, "test reason")
        interaction.followup.send.assert_awaited_once_with(
            f"{member} was banned."
        )

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
        error = client_module.discord.HTTPException(response, "sync failed")
        with patch.object(self.app.tree, "sync", AsyncMock(side_effect=error)), (
            self.assertLogs(client_module.logger, level="ERROR")
        ):
            await self.app.setup_hook()

        self.assertIsNotNone(self.app.tree.get_command("ping"))
        message = self.message("@ygg ping")
        await self.app.on_message(message)
        message.channel.send.assert_awaited_once_with("🏓 pong!")


if __name__ == "__main__":
    unittest.main()
