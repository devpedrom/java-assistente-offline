from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.config import AppConfig
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.model.client import ModelReply
from java_assistant.pdf.extract import PdfEvidence
from java_assistant.profile import DEFAULT_COMMANDS, Profile, default_profile
from java_assistant.session import AssistantSession


def profile_for(root: Path) -> Profile:
    return replace(default_profile(root), commands=DEFAULT_COMMANDS)


class CountingModel:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        requested = messages[-1].content
        if "Pedido.java" in requested:
            return ModelReply("public class Pedido { public int id; }")
        return ModelReply("public class Item { public int id; }")


class AmbiguousExtractor:
    def extract(self, _path: Path) -> PdfEvidence:
        return PdfEvidence(
            "class Pedido\n+ id: int\nclass Item\n+ id: int\nPedido -- Item\n",
            "ocr",
            (),
        )


class EmptyUnitExtractor:
    def extract(self, _path: Path) -> PdfEvidence:
        return PdfEvidence("class Vazia\n", "ocr", ())


class PlainExtractor:
    def extract(self, _path: Path) -> PdfEvidence:
        return PdfEvidence("Enunciado sem nenhuma classe.", "text", ())


class AmbiguousUmlTests(unittest.TestCase):
    def test_confirmation_does_not_promise_generation_for_incomplete_contract(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "uml.pdf").touch()
            template = root / "criterios.md"
            template.write_text("Não inventar.\n", encoding="utf-8")
            config = AppConfig(project, root / "data", root / "config", root / "state")
            model = CountingModel()
            session = AssistantSession(
                config=config,
                model=model,
                pdf_extractor=EmptyUnitExtractor(),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
            )

            try:
                session.handle("/pdf")
                asked = session.handle("1")
                blocked = session.handle("Resolva")
                confirmed = session.handle("sim")

                self.assertIn("baixa confiança", asked.text)
                self.assertIn("continua incompleto", confirmed.text)
                self.assertNotIn("Agora posso gerar", confirmed.text)
                self.assertNotIn("Solução concluída", blocked.text)
                self.assertEqual(model.calls, 0)
            finally:
                session.close()

    def test_chat_about_untrusted_contract_asks_for_confirmation_without_model_call(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "uml.pdf").touch()
            template = root / "criterios.md"
            template.write_text("Não inventar.\n", encoding="utf-8")
            model = CountingModel()
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=EmptyUnitExtractor(),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
            )

            try:
                session.handle("/pdf")
                session.handle("1")
                explained = session.handle("Explique o enunciado")
                asked_again = session.handle("O que é herança?")

                self.assertIn("baixa confiança", explained.text)
                self.assertIn("baixa confiança", asked_again.text)
                self.assertTrue(session._awaiting_contract_confirmation)
                self.assertEqual(model.calls, 0)
            finally:
                session.close()

    def test_chat_without_contract_reports_it_without_model_call(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "uml.pdf").touch()
            template = root / "criterios.md"
            template.write_text("Não inventar.\n", encoding="utf-8")
            model = CountingModel()
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=PlainExtractor(),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
            )

            try:
                session.handle("/pdf")
                session.handle("1")
                explained = session.handle("Explique o enunciado")

                self.assertIn("nenhuma unidade foi identificada", explained.text)
                self.assertFalse(session._awaiting_contract_confirmation)
                self.assertEqual(model.calls, 0)
            finally:
                session.close()

    def test_textual_correction_resolves_ambiguity_without_a_number(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "uml.pdf").touch()
            template = root / "criterios.md"
            template.write_text("Não inventar.\n", encoding="utf-8")
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=CountingModel(),
                pdf_extractor=AmbiguousExtractor(),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
            )

            try:
                session.handle("/pdf")
                session.handle("1")

                corrected = session.handle(
                    "class Pedido\n+ id: int\nclass Item\n+ id: int\n"
                    "Pedido <|-- Item\n"
                )

                self.assertNotIn("Escolha uma interpretação", corrected.text)
                self.assertIn("dados a confirmar", corrected.text)
                self.assertEqual([], session._ambiguities)

                confirmed = session.handle("sim")

                self.assertIn("Agora posso gerar", confirmed.text)
            finally:
                session.close()

    def test_generation_waits_for_user_to_choose_interpretation(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "uml.pdf").touch()
            template = root / "criterios.md"
            template.write_text("Não inventar.\n", encoding="utf-8")
            config = AppConfig(project, root / "data", root / "config", root / "state")
            model = CountingModel()
            session = AssistantSession(
                config=config,
                model=model,
                pdf_extractor=AmbiguousExtractor(),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
            )

            try:
                session.handle("/pdf")
                question = session.handle("1")
                blocked = session.handle("Resolva")

                self.assertIn("ambígu", question.text.casefold())
                self.assertIn("escolha", blocked.text.casefold())
                self.assertEqual(model.calls, 0)

                resolved = session.handle("1")
                confirmed = session.handle("sim")
                continued = session.handle("Resolva")

                self.assertIn("association", resolved.text)
                self.assertIn("baixa confiança", resolved.text)
                self.assertIn("confirmada", confirmed.text)
                self.assertIn("Solução concluída", continued.text)
                self.assertEqual(model.calls, 2)
            finally:
                session.close()


if __name__ == "__main__":
    unittest.main()
