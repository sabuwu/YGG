import logging
import os

from prompt_toolkit import PromptSession


class Terminal:
    async def start_terminal(self) -> None:
        session: PromptSession[str] = PromptSession(
            reserve_space_for_menu=0,
        )
        help_message = (
            "Comandos locais: ajuda/help para ver esta mensagem; "
            "limpar logs para limpar a tela e desabilitar os logs; "
            "ativar logs para reabilitá-los; "
            "stop/exit/quit/bye para encerrar o bot."
        )
        print("Terminal do YGG iniciado.")
        print(help_message)

        while True:
            try:
                command = (await session.prompt_async("YGG > ")).strip().casefold()
            except (EOFError, KeyboardInterrupt):
                print("\nEncerrando o bot.")
                return

            if not command:
                continue
            if command in {"stop", "exit", "quit", "bye"}:
                print("Encerrando o bot.")
                return
            if command in {"ajuda", "help"}:
                print(help_message)
                continue
            if command == "limpar logs":
                os.system("cls" if os.name == "nt" else "clear") # type: ignore
                logging.disable(logging.CRITICAL)
                print("Tela limpa; logs desabilitados.")
                continue
            if command == "ativar logs":
                logging.disable(logging.NOTSET)
                print("Logs habilitados.")
                continue

            print(f"Comando desconhecido: {command!r}. Digite ajuda para ver os comandos.")
