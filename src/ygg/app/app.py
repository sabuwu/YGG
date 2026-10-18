import asyncio
import logging
import os
import sys

import discord
from discord import app_commands
from dotenv import load_dotenv
from prompt_toolkit.patch_stdout import patch_stdout

from ygg.app.ygg_terminal.terminal import Terminal

load_dotenv()

logger = logging.getLogger(__name__)


class App(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.DISCORD_API_KEY = os.getenv("DISCORD_API_KEY")
        self.tree = app_commands.CommandTree(self)
        self.tree.command(name="ping", description="Verifica se o Ygg está respondendo.")(
            self.ping
        )

    async def setup_hook(self) -> None:
        try:
            commands = await self.tree.sync()
        except discord.HTTPException:
            logger.exception(
                "Não foi possível sincronizar os comandos /. "
                "Os comandos por mensagem continuam disponíveis."
            )
        else:
            logger.info("%d comando(s) / sincronizado(s).", len(commands))

    async def on_ready(self) -> None:
        logger.info("Conectado ao Discord como %s. Use @ygg ping ou /ping.", self.user)

    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("🏓 pong!")
        logger.info("/ping executado por %s.", interaction.user)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        parts = (message.content or "").split()
        if len(parts) != 2:
            return

        prefixes = {"@ygg"}
        if self.user is not None:
            prefixes.update({f"<@{self.user.id}>", f"<@!{self.user.id}>"})

        prefix, command = parts
        if prefix.casefold() in prefixes and command.casefold() == "ping":
            await message.channel.send("🏓 pong!")
            logger.info("%s: %s", message.author, message.content)


async def run_app(app: App, token: str) -> None:
    async with app:
        tasks = [asyncio.create_task(app.start(token), name="discord")]
        if sys.stdin.isatty():
            tasks.append(
                asyncio.create_task(Terminal().start_terminal(), name="terminal")
            )
        else:
            logger.info("Entrada sem TTY; o bot será executado sem prompt interativo.")

        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in tasks:
                if task in done:
                    task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    app = App()

    if not app.DISCORD_API_KEY:
        raise RuntimeError("DISCORD_API_KEY not found in .env")

    with patch_stdout():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            force=True,
        )

        logger.info("Iniciando Ygg...")
        try:
            asyncio.run(run_app(app, app.DISCORD_API_KEY))
        except discord.PrivilegedIntentsRequired as error:
            raise RuntimeError(
                "Ative Message Content Intent em Discord Developer Portal > "
                "Bot > Privileged Gateway Intents e reinicie o Ygg."
            ) from error
        except KeyboardInterrupt:
            print("Até mais!")
