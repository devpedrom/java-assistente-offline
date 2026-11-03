import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from java_assistant.config import AppConfig


class AppConfigTests(unittest.TestCase):
    def test_load_uses_resolved_current_directory_as_project_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.dict(os.environ, {
                "XDG_DATA_HOME": str(root / "data"),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_STATE_HOME": str(root / "state"),
            }, clear=False):
                config = AppConfig.load(root / ".")

            self.assertEqual(root.resolve(), config.project_root)
            self.assertEqual((root / "data" / "java-assistente").resolve(), config.data_dir)
            self.assertEqual((root / "config" / "java-assistente").resolve(), config.config_dir)
            self.assertEqual((root / "state" / "java-assistente").resolve(), config.state_dir)

    def test_project_root_is_immutable_during_session(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config = AppConfig.load(Path(temp_dir))

            with self.assertRaises(FrozenInstanceError):
                config.project_root = Path("/")


if __name__ == "__main__":
    unittest.main()

