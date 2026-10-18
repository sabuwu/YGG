"""Exercise command dispatch through discord.py's real Gateway event parsers."""

import asyncio
import importlib
import os
from pathlib import Path
import sys
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, patch

import discord
from discord.webhook.async_ import async_context


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
with patch("dotenv.load_dotenv"):
    app_module = importlib.import_module("ygg.app.app")


BOT_ID = 123456789
GUILD_ID = 222
CHANNEL_ID = 456
BOT_ROLE_ID = 555
OTHER_BOT_ROLE_ID = 556
ORDINARY_ROLE_ID = 557
BOT = {
    "id": str(BOT_ID),
    "username": "ygg",
    "discriminator": "0",
    "avatar": None,
    "bot": True,
}
USER = {
    "id": "123",
    "username": "gateway-test-user",
    "discriminator": "0",
    "avatar": None,
    "bot": False,
}


class GatewayCommandsTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with patch.dict(os.environ, {"DISCORD_API_KEY": "test-token"}, clear=True):
            self.app = app_module.App()
        await self.app.__aenter__()
        self.state = self.app._connection
        self.state.user = discord.ClientUser(state=self.state, data=BOT)
        self.channel = {
            "id": str(CHANNEL_ID),
            "name": "general",
            "type": 0,
            "position": 0,
            "permission_overwrites": [],
        }
        self.guild = discord.Guild(
            state=self.state,
            data={
                "id": str(GUILD_ID),
                "name": "Gateway test guild",
                "channels": [self.channel],
                "roles": [
                    {"id": str(GUILD_ID), "name": "@everyone"},
                    {
                        "id": str(OTHER_BOT_ROLE_ID),
                        "name": "ygg",
                        "managed": True,
                        "tags": {"bot_id": "987654321"},
                    },
                    {"id": str(ORDINARY_ROLE_ID), "name": "ygg"},
                    {
                        "id": str(BOT_ROLE_ID),
                        "name": "ygg",
                        "managed": True,
                        "tags": {"bot_id": str(BOT_ID)},
                    },
                ],
            },
        )
        self.state._add_guild(self.guild)
        self.send_message = AsyncMock(side_effect=self.sent_message_payload)
        self.http_patch = patch.object(
            self.app.http, "send_message", self.send_message
        )
        self.http_patch.start()

    async def asyncTearDown(self):
        self.http_patch.stop()
        await self.app.close()

    def message_payload(self, content, *, bot=False, guild=True):
        payload = {
            "id": "666",
            "channel_id": str(CHANNEL_ID),
            "author": BOT if bot else USER,
            "content": content,
            "type": 0,
            "attachments": [],
            "embeds": [],
            "mentions": [],
            "mention_roles": [str(BOT_ROLE_ID)]
            if f"<@&{BOT_ROLE_ID}>" in content
            else [],
            "timestamp": "2026-10-18T00:00:00.000000+00:00",
        }
        if guild:
            payload["guild_id"] = str(GUILD_ID)
        return payload

    def sent_message_payload(self, channel_id, *, params):
        return {
            **self.message_payload(params.payload["content"], bot=True),
            "id": "667",
            "channel_id": str(channel_id),
        }

    async def dispatch_gateway_event(self, parser, payload):
        existing_tasks = asyncio.all_tasks()
        with self.assertNoLogs(level="ERROR"):
            parser(payload)
            dispatched_tasks = asyncio.all_tasks() - existing_tasks
            if dispatched_tasks:
                await asyncio.wait_for(
                    asyncio.gather(*dispatched_tasks), timeout=1
                )

    async def dispatch_message(self, content, **kwargs):
        await self.dispatch_gateway_event(
            self.state.parse_message_create,
            self.message_payload(content, **kwargs),
        )

    def assert_pong_sent(self):
        self.send_message.assert_awaited_once()
        self.assertEqual(self.send_message.await_args.args, (CHANNEL_ID,))
        self.assertEqual(
            self.send_message.await_args.kwargs["params"].payload["content"],
            "🏓 pong!",
        )

    async def test_message_gateway_accepts_own_managed_bot_role(self):
        self.assertEqual(self.guild.self_role.id, BOT_ROLE_ID)
        for content in (f"<@&{BOT_ROLE_ID}> ping", f" <@&{BOT_ROLE_ID}>  PiNg "):
            with self.subTest(content=content):
                self.send_message.reset_mock()
                await self.dispatch_message(content)
                self.assert_pong_sent()

    async def test_message_gateway_accepts_bot_mentions_and_literal_slash_ping(self):
        for content in (
            "@ygg ping",
            f"<@{BOT_ID}> ping",
            f"<@!{BOT_ID}> ping",
            "/ping",
            "  /PiNg  ",
        ):
            with self.subTest(content=content):
                self.send_message.reset_mock()
                await self.dispatch_message(content)
                self.assert_pong_sent()

    async def test_message_gateway_ignores_other_roles_and_extra_arguments(self):
        for content in (
            f"<@&{OTHER_BOT_ROLE_ID}> ping",
            f"<@&{ORDINARY_ROLE_ID}> ping",
            f"<@&{GUILD_ID}> ping",
            "@everyone ping",
            "@here ping",
            "<@987654321> ping",
            f"<@&{BOT_ROLE_ID}> ping extra",
            "@ygg ping extra",
            "/ping extra",
        ):
            with self.subTest(content=content):
                self.send_message.reset_mock()
                await self.dispatch_message(content)
                self.send_message.assert_not_awaited()

    async def test_message_gateway_ignores_bot_authors(self):
        for content in (f"<@&{BOT_ROLE_ID}> ping", "@ygg ping", "/ping"):
            with self.subTest(content=content):
                await self.dispatch_message(content, bot=True)
                self.send_message.assert_not_awaited()

    async def test_direct_message_gateway_accepts_ping_without_guild(self):
        for content in ("@ygg ping", f"<@{BOT_ID}> ping", "/ping"):
            with self.subTest(content=content):
                self.send_message.reset_mock()
                await self.dispatch_message(content, guild=False)
                self.assert_pong_sent()

    async def test_interaction_gateway_dispatches_real_slash_ping(self):
        adapter = AsyncMock()
        adapter.create_interaction_response.return_value = {
            "interaction": {"id": "999"}
        }
        context_token = async_context.set(adapter)
        try:
            await self.dispatch_gateway_event(
                self.state.parse_interaction_create,
                {
                    "id": "999",
                    "application_id": str(BOT_ID),
                    "type": 2,
                    "token": "synthetic-interaction-token",
                    "version": 1,
                    "data": {
                        "id": "333",
                        "name": "ping",
                        "type": 1,
                        "options": [],
                    },
                    "guild_id": str(GUILD_ID),
                    "channel": self.channel,
                    "member": {
                        "user": USER,
                        "roles": [],
                        "joined_at": "2026-10-18T00:00:00.000000+00:00",
                        "deaf": False,
                        "mute": False,
                        "flags": 0,
                    },
                    "attachment_size_limit": 10000000,
                },
            )
        finally:
            async_context.reset(context_token)

        adapter.create_interaction_response.assert_awaited_once()
        payload = adapter.create_interaction_response.await_args.kwargs[
            "params"
        ].payload
        self.assertEqual(payload["type"], 4)
        self.assertEqual(payload["data"]["content"], "🏓 pong!")
        self.send_message.assert_not_awaited()


if __name__ == "__main__":
    main()
