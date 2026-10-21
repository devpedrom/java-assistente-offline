import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.config import AppConfig
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.model.client import ModelReply
from java_assistant.pdf.extract import PdfEvidence
from java_assistant.session import AssistantSession


UML = """class Main
+ Main()
+ main(args: String[]): void
"""


class ScriptedModel:
    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.calls = 0

    def complete(self, messages):
        reply = self.replies[self.calls]
        self.calls += 1
        return ModelReply(reply)


class FixedExtractor:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract(self, _path: Path) -> PdfEvidence:
        return PdfEvidence(self.text, "text", ())


class SessionFlowTests(unittest.TestCase):
    def test_pdf_choice_generation_compile_and_followup(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "Projeto com acento á"
            project.mkdir()
            (project / "Enunciado á.pdf").touch()
            template = root / "CRITERIOS_GERAIS.md"
            template.write_text("Use Java 8 e POO.\n", encoding="utf-8")
            config = AppConfig(project, root / "data", root / "config", root / "state")
            source = "public class Main { public static void main(String[] args) {} }\n"
            model = ScriptedModel(
                [
                    json.dumps({"tool": "write_file", "args": {"path": "Main.java", "content": source}}),
                    json.dumps({"tool": "compile_java", "args": {"sources": ["Main.java"]}}),
                    "Solução criada e compilada localmente.",
                    "Microajuste analisado sem perder o contexto.",
                ]
            )
            session = AssistantSession(
                config=config,
                model=model,
                pdf_extractor=FixedExtractor(UML),
                toolchain=JavaToolchain(project),
                criteria_template=template,
            )

            listing = session.handle("/pdf")
            selected = session.handle("1")
            solved = session.handle("Resolva")
            followup = session.handle("Agora revise o construtor")

            self.assertIn("1. Enunciado á.pdf", listing.text)
            self.assertIn("Main", selected.text)
            self.assertTrue((project / "Main.java").is_file())
            self.assertIn("compilada", solved.text)
            self.assertIn("Microajuste", followup.text)
            report = session.evidence.render()
            self.assertIn("## Compilado", report)
            self.assertIn("Main.java", report)
            self.assertNotIn("aprovado oficialmente", report.casefold())
            session.close()


if __name__ == "__main__":
    unittest.main()
