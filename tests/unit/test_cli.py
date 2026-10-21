from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.cli import run_cli
from java_assistant.config import AppConfig


class SequenceInput:
    def __init__(self, values: list[str]) -> None:
        self._values = iter(values)
        self.calls = 0

    def __call__(self, _prompt: str) -> str:
        self.calls += 1
        return next(self._values)


class CliTests(unittest.TestCase):
    def test_plain_text_keeps_chat_open_until_exit_command(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config = AppConfig.load(Path(temp_dir))
            input_fn = SequenceInput(["Explique polimorfismo", "/sair"])

            with redirect_stdout(StringIO()):
                result = run_cli(config, input_fn)

            self.assertEqual(0, result)
            self.assertEqual(2, input_fn.calls)

    def test_end_of_input_exits_cleanly(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config = AppConfig.load(Path(temp_dir))

            with redirect_stdout(StringIO()):
                result = run_cli(config, lambda _prompt: (_ for _ in ()).throw(EOFError))

            self.assertEqual(0, result)


if __name__ == "__main__":
    unittest.main()

