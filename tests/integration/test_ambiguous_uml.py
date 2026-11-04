from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.config import AppConfig
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.model.client import ModelReply
from java_assistant.pdf.extract import PdfEvidence
from java_assistant.session import AssistantSession


class CountingModel:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        requested = messages[-1].content
        if "Pedido.java" in requested:
            return ModelReply("public class Pedido {}")
        return ModelReply("public class Item {}")


class AmbiguousExtractor:
    def extract(self, _path: Path) -> PdfEvidence:
        return PdfEvidence("class Pedido\nclass Item\nPedido -- Item\n", "ocr", ())


class AmbiguousUmlTests(unittest.TestCase):
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
            )

            try:
                session.handle("/pdf")
                question = session.handle("1")
                blocked = session.handle("Resolva")

                self.assertIn("ambígu", question.text.casefold())
                self.assertIn("escolha", blocked.text.casefold())
                self.assertEqual(model.calls, 0)

                resolved = session.handle("1")
                continued = session.handle("Resolva")

                self.assertIn("association", resolved.text)
                self.assertIn("Solução concluída", continued.text)
                self.assertEqual(model.calls, 2)
            finally:
                session.close()


if __name__ == "__main__":
    unittest.main()
