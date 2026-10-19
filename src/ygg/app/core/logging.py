"""Configure the application's persistent log file."""

import logging
from pathlib import Path


def configure_logging() -> None:
    log_directory = Path("logs")
    log_directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        filename=str(log_directory / "ygg_logs.log"),
        encoding="utf-8",
        force=True,
    )
