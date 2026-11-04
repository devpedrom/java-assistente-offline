import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.config import AppConfig
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.model.client import ModelReply
from java_assistant.pdf.extract import PdfEvidence, PdfExtractionError
from java_assistant.session import AssistantSession


UML = """class Main
+ Main()
+ main(args: String[]): void
"""


class ScriptedModel:
    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.calls = 0

    def complete(self, messages, **_kwargs):
        reply = self.replies[self.calls]
        self.calls += 1
        return ModelReply(reply)


class RecordingScriptedModel(ScriptedModel):
    def __init__(self, replies: list[str]) -> None:
        super().__init__(replies)
        self.message_history = []

    def complete(self, messages, **_kwargs):
        self.message_history.append(list(messages))
        return super().complete(messages)


class FixedExtractor:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract(self, _path: Path) -> PdfEvidence:
        return PdfEvidence(self.text, "text", ())


class CapturingModel:
    def __init__(self) -> None:
        self.messages = []

    def complete(self, messages, **_kwargs):
        self.messages = messages
        return ModelReply("Enunciado analisado.")


class SessionFlowTests(unittest.TestCase):
    def test_next_model_call_keeps_the_actual_previous_action(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            write_block = '<write_file path="Auxiliar.java">\nclass Auxiliar {}\n</write_file>'
            model = RecordingScriptedModel(
                [
                    write_block,
                    "<compile_java />",
                    "<respond>Pronto.</respond>",
                ]
            )
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=FixedExtractor(UML),
                toolchain=JavaToolchain(project),
                criteria_template=template,
            )
            try:
                session.handle("Crie Auxiliar.java")

                self.assertIn(write_block, [item.content for item in model.message_history[1]])
            finally:
                session.close()

    def test_generation_prompt_focuses_on_one_exact_file(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "enunciado.pdf").touch()
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            model = CapturingModel()
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=FixedExtractor(UML),
                toolchain=JavaToolchain(project),
                criteria_template=template,
            )
            try:
                session.handle("/pdf")
                session.handle("1")
                session.handle("Resolva")

                self.assertIn("SOMENTE Main.java", model.messages[-1].content)
                self.assertTrue(
                    any("public Main();" in item.content for item in model.messages)
                )
                self.assertTrue(
                    any(
                        "public void main(String[] args);" in item.content
                        for item in model.messages
                    )
                )
            finally:
                session.close()

    def test_detects_main_class_from_uml_method_even_with_custom_class_name(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "enunciado.pdf").touch()
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=CapturingModel(),
                pdf_extractor=FixedExtractor(
                    "CLASSE: Aplicacao\n+ main(args: String[]): void\n"
                ),
                toolchain=JavaToolchain(project),
                criteria_template=template,
            )
            try:
                session.handle("/pdf")
                session.handle("1")

                self.assertEqual("Aplicacao", session._main_class_name())
            finally:
                session.close()

    def test_model_receives_method_rules_from_selected_pdf(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "frota.pdf").touch()
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            model = CapturingModel()
            pdf_text = """CLASSE: Pickup
+ autonomia(): Double
Caso esteja totalmente carregada a autonomia e reduzida pela metade.
"""
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=FixedExtractor(pdf_text),
                toolchain=JavaToolchain(project),
                criteria_template=template,
            )
            try:
                session.handle("/pdf")
                session.handle("1")
                session.handle("Resolva o exercicio")

                self.assertTrue(
                    any("reduzida pela metade" in item.content for item in model.messages)
                )
                self.assertTrue(
                    any("public Double autonomia();" in item.content for item in model.messages)
                )
                self.assertTrue(
                    any("construtor vazio" in item.content for item in model.messages)
                )
            finally:
                session.close()

    def test_generation_prompt_expands_percentage_rules_into_exact_factors(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "hatch.pdf").touch()
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            model = CapturingModel()
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=FixedExtractor(
                    "CLASSE: Hatch\n+ calculaVolume(int): Double\n"
                    "O volume aumenta em 100% ou aumenta em 50%.\n"
                ),
                toolchain=JavaToolchain(project),
                criteria_template=template,
            )
            try:
                session.handle("/pdf")
                session.handle("1")
                session.handle("Resolva")

                prompt = "\n".join(item.content for item in model.messages)
                self.assertIn("base * 2.0", prompt)
                self.assertIn("base * 1.5", prompt)
            finally:
                session.close()

    def test_main_prompt_does_not_inherit_arithmetic_rules_from_other_classes(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "frota.pdf").touch()
            (project / "Hatch.java").write_text(
                "public class Hatch {}\n", encoding="utf-8"
            )
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            model = CapturingModel()
            pdf_text = """CLASSE: Hatch
+ calculaVolume(int): Double
O volume aumenta em 100% ou aumenta em 50%.

INSTRUÇÃO FINAL
Crie uma classe Frota (main) que teste os métodos.
"""
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=FixedExtractor(pdf_text),
                toolchain=JavaToolchain(project),
                criteria_template=template,
            )
            try:
                session.handle("/pdf")
                session.handle("1")
                session.handle("Resolva")

                prompt = "\n".join(item.content for item in model.messages)
                self.assertIn("SOMENTE Frota.java", prompt)
                self.assertNotIn("base * 2.0", prompt)
                self.assertNotIn("base * 1.5", prompt)
            finally:
                session.close()

    def test_guided_generation_repairs_compiling_code_that_diverges_from_uml(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "enunciado.pdf").touch()
            template = root / "criterios.md"
            template.write_text("Preserve exatamente os tipos do UML.\n", encoding="utf-8")
            model = ScriptedModel(
                [
                    "public class Conta { public double total() { return 0.0; } }",
                    "public class Conta { public Double total() { return 0.0; } }",
                ]
            )
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=FixedExtractor("class Conta\n+ total(): Double\n"),
                toolchain=JavaToolchain(project),
                criteria_template=template,
            )
            try:
                session.handle("/pdf")
                session.handle("1")
                solved = session.handle("Resolva")

                self.assertIn("compilação Java 8 aprovada", solved.text)
                self.assertEqual(model.calls, 2)
                self.assertIn("Double total()", (project / "Conta.java").read_text(encoding="utf-8"))
            finally:
                session.close()

    def test_solve_reenters_guided_pipeline_when_all_sources_already_exist(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "enunciado.pdf").touch()
            (project / "Main.java").write_text(
                "public class Main { public static void main(String[] args) { missing(); } }\n",
                encoding="utf-8",
            )
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            model = ScriptedModel(
                ["public class Main { public static void main(String[] args) {} }"]
            )
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=FixedExtractor(UML),
                toolchain=JavaToolchain(project),
                criteria_template=template,
            )
            try:
                session.handle("/pdf")
                session.handle("1")
                solved = session.handle("Resolva")

                self.assertIn("compilação Java 8 aprovada", solved.text)
                self.assertEqual(1, model.calls)
            finally:
                session.close()

    def test_one_request_can_create_more_than_three_files(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            replies = [
                json.dumps(
                    {"tool": "write_file", "args": {"path": f"Classe{number}.java", "content": f"class Classe{number} {{}}\n"}}
                )
                for number in range(1, 5)
            ] + [json.dumps({"tool": "respond", "args": {"text": "Quatro classes criadas."}})]
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=ScriptedModel(replies),
                pdf_extractor=FixedExtractor(UML),
                toolchain=JavaToolchain(project),
                criteria_template=template,
            )
            try:
                result = session.handle("Crie quatro classes")

                self.assertIn("Quatro classes", result.text)
                self.assertTrue(
                    all(
                        (project / f"Classe{number}.java").is_file()
                        for number in range(1, 5)
                    )
                )
            finally:
                session.close()

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
                    source,
                    json.dumps({"tool": "respond", "args": {"text": "Microajuste analisado sem perder o contexto."}}),
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
            self.assertIn("compilação Java 8 aprovada", solved.text)
            self.assertIn("Microajuste", followup.text)
            report = session.evidence.render()
            self.assertIn("## Compilado", report)
            self.assertIn("Main.java", report)
            self.assertNotIn("aprovado oficialmente", report.casefold())
            session.close()


class PastedEnunciadoTests(unittest.TestCase):
    def _session(self, root: Path) -> AssistantSession:
        project = root / "projeto"
        project.mkdir()
        template = root / "criterios.md"
        template.write_text("Java POO.\n", encoding="utf-8")
        return AssistantSession(
            config=AppConfig(project, root / "data", root / "config", root / "state"),
            model=ScriptedModel([]),
            pdf_extractor=FixedExtractor(""),
            toolchain=JavaToolchain(project),
            criteria_template=template,
        )

    def test_pasted_text_enunciado_produces_same_contract_as_pdf(self) -> None:
        with TemporaryDirectory() as temp:
            session = self._session(Path(temp))
            try:
                session.handle("/enunciado")
                session.handle("CLASSE: Conta\n- saldo: int\n+ Conta(int)")
                reply = session.handle("/fim")

                self.assertIn("Conta", reply.text)
                assert session._contract is not None
                self.assertEqual([item.name for item in session._contract.classes], ["Conta"])
            finally:
                session.close()

    def test_pasted_text_without_classes_asks_instead_of_generating(self) -> None:
        with TemporaryDirectory() as temp:
            session = self._session(Path(temp))
            try:
                session.handle("/enunciado")
                session.handle("texto qualquer sem diagrama")
                reply = session.handle("/fim")

                self.assertIn("não reconheci", reply.text.casefold())
                self.assertIsNone(session._contract)
            finally:
                session.close()

    def test_paste_mode_is_cancelled_by_sair(self) -> None:
        with TemporaryDirectory() as temp:
            session = self._session(Path(temp))
            try:
                session.handle("/enunciado")
                reply = session.handle("/sair")

                self.assertTrue(reply.exit_requested)
            finally:
                session.close()


class FailingExtractor:
    def extract(self, _path: Path) -> PdfEvidence:
        raise PdfExtractionError("PDF ilegível")


class FailureBoundaryTests(unittest.TestCase):
    def _session(self, root: Path, extractor, model) -> AssistantSession:
        project = root / "projeto"
        project.mkdir()
        (project / "enunciado.pdf").touch()
        template = root / "criterios.md"
        template.write_text("Java POO.\n", encoding="utf-8")
        return AssistantSession(
            config=AppConfig(project, root / "data", root / "config", root / "state"),
            model=model,
            pdf_extractor=extractor,
            toolchain=JavaToolchain(project),
            criteria_template=template,
        )

    def test_unreadable_pdf_keeps_chat_alive(self) -> None:
        with TemporaryDirectory() as temp:
            session = self._session(Path(temp), FailingExtractor(), ScriptedModel([]))
            try:
                self.assertIn("enunciado.pdf", session.handle("/pdf").text)
                reply = session.handle("1")

                self.assertIn("Não consegui concluir", reply.text)
                self.assertIn("PDF ilegível", reply.text)
                self.assertFalse(reply.exit_requested)
                self.assertIn("enunciado.pdf", session.handle("/pdf").text)
            finally:
                session.close()

    def test_model_failure_keeps_chat_alive(self) -> None:
        class BrokenModel:
            def complete(self, _messages, **_kwargs):
                raise RuntimeError("modelo local parou")

        with TemporaryDirectory() as temp:
            session = self._session(Path(temp), FixedExtractor(""), BrokenModel())
            try:
                reply = session.handle("Resolva o exercício")

                self.assertIn("modelo local parou", reply.text)
                self.assertFalse(reply.exit_requested)
            finally:
                session.close()

    def test_truncated_reply_asks_instead_of_blaming_the_code(self) -> None:
        class TruncatedModel:
            def complete(self, _messages, **_kwargs):
                return ModelReply("class Conta {", truncated=True)

        with TemporaryDirectory() as temp:
            session = self._session(Path(temp), FixedExtractor(""), TruncatedModel())
            try:
                session.handle("/enunciado")
                session.handle("CLASSE: Conta\n- saldo: double")
                session.handle("/fim")
                reply = session.handle("Resolva")

                self.assertIn("cortada", reply.text)
                self.assertNotIn("compilação", reply.text.casefold())
            finally:
                session.close()


if __name__ == "__main__":
    unittest.main()
