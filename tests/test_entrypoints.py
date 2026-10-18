from contextlib import nullcontext
import importlib
import importlib.util
import os
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "src" / "ygg" / "app" / "app.py"
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class EntrypointTests(unittest.TestCase):
    def test_direct_app_execution_starts_app_once(self):
        def close_without_running(coroutine):
            coroutine.close()

        with (
            patch("dotenv.load_dotenv"),
            patch.dict(os.environ, {"DISCORD_API_KEY": "test-discord-token"}, clear=True),
            patch("prompt_toolkit.patch_stdout.patch_stdout", return_value=nullcontext()),
            patch("pathlib.Path.mkdir") as mkdir,
            patch("logging.basicConfig") as basic_config,
            patch("asyncio.run", side_effect=close_without_running) as run,
        ):
            runpy.run_path(str(APP_PATH), run_name="__main__")

        run.assert_called_once()
        self.assertEqual(run.call_args.args[0].cr_code.co_name, "run_app")
        mkdir.assert_called_once_with(parents=True, exist_ok=True)
        self.assertEqual(
            basic_config.call_args.kwargs["filename"], "logs/ygg_logs.log"
        )

    def test_package_execution_calls_main_once(self):
        with patch("dotenv.load_dotenv"):
            app_module = importlib.import_module("ygg.app.app")

        with patch.object(app_module, "main") as main:
            runpy.run_module("ygg", run_name="__main__")

        main.assert_called_once_with()

    def test_importing_app_does_not_start_it(self):
        spec = importlib.util.spec_from_file_location("ygg.app._import_test", APP_PATH)
        module = importlib.util.module_from_spec(spec)

        with patch("dotenv.load_dotenv"), patch("asyncio.run") as run:
            spec.loader.exec_module(module)

        self.assertTrue(callable(module.main))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
