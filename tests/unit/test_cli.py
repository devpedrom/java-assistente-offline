from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from java_assistant.cli import main, run_cli
from java_assistant.config import AppConfig
from java_assistant.profile import default_profile
from java_assistant.session import SessionReply


class SequenceInput:
    def __init__(self, values: list[str]) -> None:
        self._values = iter(values)
        self.calls = 0

    def __call__(self, _prompt: str) -> str:
        self.calls += 1
        return next(self._values)


class CliTests(unittest.TestCase):
    def test_runtime_is_stopped_even_when_session_close_raises(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = AppConfig.load(root)
            profile = default_profile(root)
            class Runtime:
                port = 12345
                running = False
                def start(self):
                    self.running = True
                def stop(self):
                    self.running = False
            runtime = Runtime()
            class Session:
                def __init__(self, **kwargs):
                    pass
                def close(self):
                    raise RuntimeError("falha ao fechar sessão")
            with mock.patch.dict(os.environ, {"JAVA_ASSISTANT_HOME": str(root)}), \
                 mock.patch("java_assistant.cli.AppConfig.load", return_value=config), \
                 mock.patch("java_assistant.cli.ensure_profile"), \
                 mock.patch("java_assistant.cli.load_profile", return_value=profile), \
                 mock.patch("java_assistant.cli.verify_paths"), \
                 mock.patch("java_assistant.cli.LlamaRuntime", return_value=runtime), \
                 mock.patch("java_assistant.cli.AssistantSession", Session), \
                 mock.patch("java_assistant.cli.run_cli", return_value=0):
                with self.assertRaisesRegex(RuntimeError, "falha ao fechar sessão"):
                    main()
            self.assertFalse(runtime.running)

    def test_routes_commands_through_session_and_prints_reply(self) -> None:
        class FakeSession:
            def __init__(self) -> None:
                self.received: list[str] = []

            def handle(self, text: str) -> SessionReply:
                self.received.append(text)
                return SessionReply("resposta pronta", text == "/sair")

        with TemporaryDirectory() as temp_dir:
            config = AppConfig.load(Path(temp_dir))
            input_fn = SequenceInput(["/pdf", "/sair"])
            session = FakeSession()
            output = StringIO()

            with redirect_stdout(output):
                result = run_cli(config, input_fn, session=session)

            self.assertEqual(result, 0)
            self.assertEqual(session.received, ["/pdf", "/sair"])
            self.assertIn("resposta pronta", output.getvalue())

    def test_plain_text_keeps_chat_open_until_exit_command(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config = AppConfig.load(Path(temp_dir))
            input_fn = SequenceInput(["Explique polimorfismo", "/sair"])

            with redirect_stdout(StringIO()):
                result = run_cli(config, input_fn)

            self.assertEqual(0, result)
            self.assertEqual(2, input_fn.calls)

    def test_static_help_before_the_model_lists_profile(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config = AppConfig.load(Path(temp_dir))
            input_fn = SequenceInput(["/ajuda", "/sair"])
            output = StringIO()

            with redirect_stdout(output):
                result = run_cli(config, input_fn)

        self.assertEqual(0, result)
        self.assertIn("/perfil", output.getvalue())
        self.assertNotIn("Modelo local ainda não iniciado.", output.getvalue())

    def test_main_applies_profile_limits_to_runtime_model_and_toolchain(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = AppConfig.load(root)
            base = default_profile(root)
            profile = replace(
                base,
                limits=replace(
                    base.limits,
                    context_tokens=1024,
                    output_tokens=128,
                    inspect_timeout_s=3,
                ),
            )
            captured = {}

            class FakeRuntime:
                def __init__(self, runtime_config):
                    captured["runtime_config"] = runtime_config
                    self.port = 12345

                def start(self):
                    pass

                def stop(self):
                    pass

            class FakeSession:
                def __init__(self, **kwargs):
                    captured["session"] = kwargs

                def close(self):
                    pass

            with mock.patch.dict(os.environ, {"JAVA_ASSISTANT_HOME": str(root)}), \
                mock.patch("java_assistant.cli.AppConfig") as config_class, \
                mock.patch("java_assistant.cli.ensure_profile"), \
                mock.patch("java_assistant.cli.load_profile", return_value=profile), \
                mock.patch("java_assistant.cli.verify_paths"), \
                mock.patch("java_assistant.cli.LlamaRuntime", FakeRuntime), \
                mock.patch("java_assistant.cli.AssistantSession", FakeSession), \
                mock.patch("java_assistant.cli.run_cli", return_value=0):
                config_class.load.return_value = config
                self.assertEqual(0, main())

            self.assertEqual(1024, captured["runtime_config"].context_size)
            transport = captured["session"]["model"]._transport
            self.assertEqual(128, transport._max_tokens)
            self.assertEqual(3, captured["session"]["toolchain"].inspect_timeout_s)

    def test_end_of_input_exits_cleanly(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config = AppConfig.load(Path(temp_dir))

            with redirect_stdout(StringIO()):
                result = run_cli(config, lambda _prompt: (_ for _ in ()).throw(EOFError))

            self.assertEqual(0, result)


if __name__ == "__main__":
    unittest.main()
