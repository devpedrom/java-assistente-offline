from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest

from java_assistant.config import AppConfig
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.model.client import ModelReply
from java_assistant.pdf.extract import PdfEvidence
from java_assistant.profile import DEFAULT_COMMANDS, Profile, default_profile
from java_assistant.session import AssistantSession


def profile_for(root: Path) -> Profile:
    return replace(default_profile(root), commands=DEFAULT_COMMANDS)


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


class RecordingScriptedModel(ScriptedModel):
    def __init__(self, replies: list[str]) -> None:
        super().__init__(replies)
        self.message_history = []

    def complete(self, messages):
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

    def complete(self, messages):
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
                profile=profile_for(root),
            )
            try:
                reply = session.handle("Crie Auxiliar.java")

                self.assertIn(write_block, [item.content for item in model.message_history[1]])
                self.assertNotIn("Não confirmei", reply.text)
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
                profile=profile_for(root),
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
                        "public static void main(String[] args);" in item.content
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
                    "CLASSE: Aplicacao\n+ main(String[] args): void\n"
                ),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
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
                profile=profile_for(root),
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
                profile=profile_for(root),
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

CLASSE: Frota
+ main(args: String[]): void

INSTRUÇÃO FINAL
Crie a classe Frota que teste os métodos.
"""
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=FixedExtractor(pdf_text),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
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
                profile=profile_for(root),
            )
            try:
                session.handle("/pdf")
                session.handle("1")
                solved = session.handle("Resolva")

                self.assertIn("Solução concluída", solved.text)
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
                profile=profile_for(root),
            )
            try:
                session.handle("/pdf")
                session.handle("1")
                solved = session.handle("Resolva")

                self.assertIn("Solução concluída", solved.text)
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
                profile=profile_for(root),
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
                profile=profile_for(root),
            )

            listing = session.handle("/pdf")
            selected = session.handle("1")
            solved = session.handle("Resolva")
            followup = session.handle("Agora revise o construtor")

            self.assertIn("1. Enunciado á.pdf", listing.text)
            self.assertIn("Main", selected.text)
            self.assertTrue((project / "Main.java").is_file())
            self.assertIn("Solução concluída", solved.text)
            self.assertIn("Microajuste", followup.text)
            report = session.evidence.render()
            self.assertIn("## Compilado", report)
            self.assertIn("Main.java", report)
            self.assertNotIn("aprovado oficialmente", report.casefold())
            session.close()

    def test_relationship_cycle_does_not_hang_the_focused_context(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            (project / "enunciado.pdf").touch()
            (project / "A.java").write_text("public class A {}\n", encoding="utf-8")
            (project / "B.java").write_text("public class B {}\n", encoding="utf-8")
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=CapturingModel(),
                pdf_extractor=FixedExtractor(
                    "class A\nclass B\nA <|-- B\nB <|-- A\n"
                ),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
            )
            try:
                session.handle("/pdf")
                session.handle("1")
                selected: dict[str, str] = {}
                worker = threading.Thread(
                    target=lambda: selected.update(session._focused_relevant_files("A")),
                    daemon=True,
                )
                worker.start()
                worker.join(10)

                self.assertFalse(worker.is_alive(), "ciclo de herança travou o contexto")
                self.assertIn("A.java", selected)
                self.assertIn("B.java", selected)
            finally:
                session.close()

    def test_ambiguous_entry_is_chosen_by_the_name_in_the_request(self) -> None:
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
                    "class App\n+ main(args: String[]): void\n"
                    "class Zapp\n+ main(args: String[]): void\n"
                ),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
            )
            try:
                session.handle("/pdf")
                session.handle("1")

                self.assertEqual("Zapp", session._named_entry("Implemente Zapp"))
                self.assertIsNone(session._named_entry("Implemente as duas"))
            finally:
                session.close()

    def test_profile_limits_reach_the_context_budget(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            base = profile_for(root)
            profile = replace(
                base,
                limits=replace(
                    base.limits, context_tokens=1024, output_tokens=128
                ),
                context=replace(
                    base.context, chars_per_token=2.0, sections={"protocol": 10}
                ),
            )
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=CapturingModel(),
                pdf_extractor=FixedExtractor(UML),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile,
            )
            try:
                budget = session._budget()

                self.assertEqual(1024, budget.context_tokens)
                self.assertEqual(128, budget.output_tokens)
                self.assertEqual(2.0, budget.chars_per_token)
                self.assertEqual({"protocol": 10}, dict(budget.sections))
            finally:
                session.close()

    def test_warning_appears_when_the_compile_action_is_refused(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            model = ScriptedModel(
                [
                    json.dumps(
                        {
                            "tool": "write_file",
                            "args": {"path": "Solta.java", "content": "class Solta {}\n"},
                        }
                    ),
                    json.dumps(
                        {"tool": "compile_java", "args": {"sources": "Solta.java"}}
                    ),
                    json.dumps({"tool": "respond", "args": {"text": "Pronto."}}),
                ]
            )
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=FixedExtractor(UML),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
            )
            try:
                result = session.handle("Crie Solta.java")

                self.assertIn("Não confirmei a solução", result.text)
            finally:
                session.close()

    def test_chat_warns_when_a_file_is_written_without_verification(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            model = ScriptedModel(
                [
                    json.dumps(
                        {
                            "tool": "write_file",
                            "args": {"path": "Solta.java", "content": "class Solta {}\n"},
                        }
                    ),
                    json.dumps({"tool": "respond", "args": {"text": "Pronto."}}),
                ]
            )
            session = AssistantSession(
                config=AppConfig(project, root / "data", root / "config", root / "state"),
                model=model,
                pdf_extractor=FixedExtractor(UML),
                toolchain=JavaToolchain(project),
                criteria_template=template,
                profile=profile_for(root),
            )
            try:
                result = session.handle("Crie Solta.java")

                self.assertIn("Não confirmei a solução", result.text)
                self.assertIn("Pronto.", result.text)
            finally:
                session.close()

    def test_rejects_profile_extension_that_does_not_match_the_adapter(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "projeto"
            project.mkdir()
            template = root / "criterios.md"
            template.write_text("Java POO.\n", encoding="utf-8")
            profile = replace(profile_for(root), source_extension=".txt")

            with self.assertRaisesRegex(ValueError, "extensão do perfil"):
                AssistantSession(
                    config=AppConfig(
                        project, root / "data", root / "config", root / "state"
                    ),
                    model=CapturingModel(),
                    pdf_extractor=FixedExtractor(UML),
                    toolchain=JavaToolchain(project),
                    criteria_template=template,
                    profile=profile,
                )


if __name__ == "__main__":
    unittest.main()
