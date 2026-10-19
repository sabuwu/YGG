import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from dotenv import load_dotenv


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ygg.app.core.config import load_token


class ConfigTests(unittest.TestCase):
    def test_missing_or_empty_token_fails_without_reading_real_env_file(self):
        for environment in ({}, {"DISCORD_API_KEY": ""}):
            with self.subTest(environment=environment), (
                patch.dict(os.environ, environment, clear=True)
            ), patch("ygg.app.core.config.load_dotenv"):
                with self.assertRaisesRegex(RuntimeError, "DISCORD_API_KEY not found in .env"):
                    load_token()

    def test_loads_env_file_and_preserves_process_environment_precedence(self):
        with TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("DISCORD_API_KEY=token-from-test-file\n")
            for environment, expected in (
                ({}, "token-from-test-file"),
                ({"DISCORD_API_KEY": "token-from-test-process"}, "token-from-test-process"),
            ):
                with self.subTest(environment=environment), (
                    patch.dict(os.environ, environment, clear=True)
                ), patch(
                    "ygg.app.core.config.load_dotenv",
                    side_effect=lambda: load_dotenv(env_path),
                ):
                    self.assertEqual(load_token(), expected)


if __name__ == "__main__":
    unittest.main()
