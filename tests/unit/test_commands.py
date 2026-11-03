from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType
import unittest

from java_assistant.config import AppConfig
from java_assistant.core.commands import CommandRegistry
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.model.client import ModelReply
from java_assistant.pdf.extract import PdfEvidence
from java_assistant.profile import DEFAULT_COMMANDS, default_profile
from java_assistant.session import AssistantSession


class SilentModel:
    def __init__(self, replies: list[str] | None = None) -> None:
        self.replies = list(replies or [])
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        return ModelReply(self.replies.pop(0) if self.replies else "resposta")


class EmptyExtractor:
    def extract(self, _path: Path) -> PdfEvidence:
        return PdfEvidence("", "text", ())


def registry(**commands: tuple[str, ...]) -> CommandRegistry:
    values = dict(DEFAULT_COMMANDS)
    values.update(commands)
    return CommandRegistry.from_profile(values)


class CommandRegistryTests(unittest.TestCase):
    def test_resolves_renamed_and_disabled_commands(self) -> None:
        renamed = registry(
            pdf=("/enunciado",),
            undo=("/voltar",),
            exit=("/fim", "tchau"),
        )
        disabled = {key: value for key, value in DEFAULT_COMMANDS.items() if key != "pdf"}

        self.assertEqual("pdf", renamed.resolve(" /ENUNCIADO "))
        self.assertEqual("exit", renamed.resolve("tchau"))
        self.assertIsNone(renamed.resolve("/pdf"))
        self.assertIsNone(
            CommandRegistry.from_profile(disabled).resolve("/pdf")
        )

    def test_unknown_command_returns_none_and_help_lists_only_active_aliases(
        self,
    ) -> None:
        registry_ = CommandRegistry.from_profile(
            {key: value for key, value in DEFAULT_COMMANDS.items() if key != "pdf"}
        )

        self.assertIsNone(registry_.resolve("/pdf"))
        self.assertIsNone(registry_.resolve("/nada"))
        self.assertNotIn("/pdf", registry_.help_text())
        self.assertIn("/sair", registry_.help_text())

    def test_help_text_is_generated_from_profile_order(self) -> None:
        text = registry(exit=("/fim",)).help_text()
        positions = [
            text.index(alias)
            for alias in ("/pdf", "/desfazer", "/relatorio", "/perfil", "/ajuda", "/fim")
        ]

        self.assertEqual(sorted(positions), positions)

    def test_rejects_empty_alias_duplicate_unknown_and_missing_exit(self) -> None:
        for commands in (
            {"exit": ()},
            {"exit": ("/sair",), "pdf": ("/sair",)},
            {"exit": ("/sair",), "unknown": ("/x",)},
            {"pdf": ("/pdf",)},
        ):
            with self.assertRaises(ValueError):
                CommandRegistry.from_profile(commands)


class SessionCommandTests(unittest.TestCase):
    def _session(self, root: Path, commands: dict[str, tuple[str, ...]]):
        project = root / "projeto"
        project.mkdir()
        template = root / "criterios.md"
        template.write_text("Java POO.\n", encoding="utf-8")
        profile = replace(
            default_profile(root), commands=MappingProxyType(commands)
        )
        model = SilentModel()
        session = AssistantSession(
            config=AppConfig(project, root / "dados", root / "config", root / "estado"),
            model=model,
            pdf_extractor=EmptyExtractor(),
            toolchain=JavaToolchain(project),
            criteria_template=template,
            profile=profile,
        )
        return session, model

    def test_session_uses_the_configured_aliases(self) -> None:
        with TemporaryDirectory() as temp:
            session, model = self._session(
                Path(temp), {**DEFAULT_COMMANDS, "exit": ("/fim",)}
            )
            try:
                reply = session.handle("/fim")
                self.assertTrue(reply.exit_requested)
                self.assertEqual(0, model.calls)

                fallback = session.handle("/sair")
                self.assertFalse(fallback.exit_requested)
                self.assertEqual(0, model.calls)
                self.assertIn("/fim", fallback.text)

                unknown = session.handle("/comando-inexistente")
                self.assertIn("/fim", unknown.text)
                self.assertEqual(0, model.calls)
            finally:
                session.close()

    def test_profile_command_shows_paths_limits_and_aliases(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            session, model = self._session(root, dict(DEFAULT_COMMANDS))
            try:
                reply = session.handle("/perfil")
            finally:
                session.close()

        self.assertIn(str(root / "perfil.json"), reply.text)
        self.assertIn("projeto: nenhum", reply.text)
        self.assertIn("origem: global", reply.text)
        self.assertIn("java8", reply.text)
        self.assertIn("4096", reply.text)
        self.assertIn("saída 640", reply.text)
        self.assertIn("reparos 2", reply.text)
        self.assertIn("arquivos 40", reply.text)
        self.assertIn("/perfil", reply.text)
        self.assertGreater(reply.text.index("Comandos:"), reply.text.index("origem:"))
        self.assertEqual(0, model.calls)


if __name__ == "__main__":
    unittest.main()
