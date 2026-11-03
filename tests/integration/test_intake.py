"""Textual intake: a user answer can complete or correct an untrusted contract."""

from dataclasses import replace
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from java_assistant.adapters.base import CompileResult, RunResult
from java_assistant.config import AppConfig
from java_assistant.core.solver import ContractStatus, classify
from java_assistant.core.facts import extract_rules
from java_assistant.model.client import ModelReply
from java_assistant.pdf.extract import PdfEvidence
from java_assistant.profile import DEFAULT_COMMANDS, Profile, default_profile
from java_assistant.session import AssistantSession


def profile_for(root: Path) -> Profile:
    return replace(default_profile(root), commands=DEFAULT_COMMANDS)


class FixedExtractor:
    def __init__(self, text: str, source: str = "text") -> None:
        self.text = text
        self.source = source

    def extract(self, _path: Path) -> PdfEvidence:
        return PdfEvidence(self.text, self.source, ())


class CountingModel:
    def __init__(self, replies: list[str] | None = None) -> None:
        self.calls = 0
        self.replies = list(replies or [])

    def complete(self, messages):
        self.calls += 1
        if not self.replies:
            raise AssertionError("o intake não deveria chamar o modelo")
        return ModelReply(self.replies.pop(0))


class NoToolchain:
    def compile(self, *args, **kwargs):
        raise AssertionError("o intake não deveria compilar")

    def run(self, *args, **kwargs):
        raise AssertionError("o intake não deveria executar")

    def inspect(self, *args, **kwargs):
        raise AssertionError("o intake não deveria inspecionar")


class OkToolchain:
    def compile(self, sources, timeout_s: int = 30) -> CompileResult:
        return CompileResult(True, "", Path.cwd(), ("fake",))

    def run(self, main_class, timeout_s, args=(), stdin="") -> RunResult:
        return RunResult(True, "", "", 0, False)

    def inspect(self, symbol, timeout_s: int = 10) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [], 0, "public double total();", ""
        )


class IntakeTests(unittest.TestCase):
    def _root(self) -> Path:
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def _session(
        self,
        root: Path,
        text: str,
        *,
        source: str = "text",
        model=None,
        toolchain=None,
    ):
        project = root / "projeto"
        project.mkdir()
        (project / "enunciado.pdf").touch()
        template = root / "criterios.md"
        template.write_text("Java POO.\n", encoding="utf-8")
        model = model or CountingModel()
        session = AssistantSession(
            config=AppConfig(project, root / "data", root / "config", root / "state"),
            model=model,
            pdf_extractor=FixedExtractor(text, source),
            toolchain=toolchain or NoToolchain(),
            criteria_template=template,
            profile=profile_for(root),
        )
        self.addCleanup(session.close)
        session.handle("/pdf")
        session.handle("1")
        return session, project, model

    def test_no_contract_is_built_from_the_user_text(self) -> None:
        root = self._root()
        session, _project, model = self._session(root, "Enunciado sem classes.\n")

        updated = session.handle(
            "Enunciado sem classes.\n"
            "class Conta\n+ total(): double\n"
            "Aplique o fator informado.\n"
        )

        self.assertIn("Agora posso gerar", updated.text)
        self.assertIs(ContractStatus.TRUSTED, classify(session._contract))
        self.assertEqual(["Conta"], [unit.name for unit in session._contract.units])
        self.assertTrue(
            any(
                "Aplique o fator informado." in requirement.text
                for requirement in session._contract.requirements
            )
        )
        self.assertEqual(
            "user",
            next(
                requirement.origin
                for requirement in session._contract.requirements
                if requirement.scope == "Conta"
            ),
        )
        self.assertEqual(
            1,
            len(
                [
                    requirement
                    for requirement in session._contract.requirements
                    if requirement.text == "Enunciado sem classes."
                ]
            ),
        )
        self.assertTrue(
            any(
                "Contrato textual do usuário" in item
                for item in session.evidence.observations
            )
        )
        self.assertEqual(0, model.calls)

    def test_trusted_contract_after_intake_reaches_the_solver(self) -> None:
        root = self._root()
        model = CountingModel(
            ["public class Conta { public double total() { return 1.0; } }"]
        )
        session, project, _model = self._session(
            root,
            "Enunciado sem classes.\n",
            model=model,
            toolchain=OkToolchain(),
        )
        session.handle("class Conta\n+ total(): double\n")

        solved = session.handle("Resolva")

        self.assertIn("Solução concluída", solved.text)
        self.assertEqual(1, model.calls)
        self.assertTrue((project / "Conta.java").is_file())

    def test_textual_correction_completes_an_incomplete_unit(self) -> None:
        root = self._root()
        session, _project, model = self._session(root, "class Conta\n")

        updated = session.handle(
            "class Conta\n+ total(): double\nRegra da unidade.\n"
        )

        self.assertIn("Agora posso gerar", updated.text)
        self.assertIs(ContractStatus.TRUSTED, classify(session._contract))
        self.assertEqual(
            ["total"], [member.name for member in session._contract.units[0].members]
        )
        self.assertEqual(0, model.calls)

    def test_invalid_correction_keeps_the_block(self) -> None:
        root = self._root()
        session, project, model = self._session(root, "class Conta\n")

        blocked = session.handle("Ainda não sei.")

        self.assertIn("baixa confiança", blocked.text)
        self.assertIs(ContractStatus.NEEDS_CONFIRMATION, classify(session._contract))
        self.assertEqual(0, model.calls)
        self.assertEqual([], list(project.glob("*.java")))

    def test_intake_never_calls_model_compiles_or_writes(self) -> None:
        root = self._root()
        session, project, model = self._session(root, "Enunciado sem classes.\n")

        session.handle("class Conta\n+ total(): double\n")

        self.assertEqual(0, model.calls)
        self.assertEqual(["enunciado.pdf"], [path.name for path in project.iterdir()])

    def test_simple_confirmation_does_not_invent_missing_members(self) -> None:
        root = self._root()
        session, _project, model = self._session(root, "class Vazia\n")

        confirmed = session.handle("sim")

        self.assertIn("continua incompleto", confirmed.text)
        self.assertIs(ContractStatus.NEEDS_CONFIRMATION, classify(session._contract))
        self.assertEqual((), session._contract.units[0].members)
        self.assertEqual(0, model.calls)

    def test_valid_correction_does_not_repeat_the_same_question(self) -> None:
        root = self._root()
        session, _project, _model = self._session(root, "Enunciado sem classes.\n")
        first = session.handle("Explique o enunciado").text

        second = session.handle("class Conta\n+ total(): double\n").text

        self.assertIn("nenhuma unidade foi identificada", first)
        self.assertNotEqual(first, second)
        self.assertNotIn("nenhuma unidade foi identificada", second)
        self.assertIs(ContractStatus.TRUSTED, classify(session._contract))

    def test_user_unit_without_members_does_not_erase_pdf_members(self) -> None:
        root = self._root()
        session, _project, _model = self._session(
            root,
            "class Conta\n+ total(): double\n",
            source="ocr",
        )

        session.handle("class Conta\n")

        self.assertEqual(
            ["total"], [member.name for member in session._contract.units[0].members]
        )
        self.assertIs(ContractStatus.NEEDS_CONFIRMATION, classify(session._contract))

    def test_partial_correction_keeps_members_the_user_did_not_mention(self) -> None:
        root = self._root()
        session, _project, _model = self._session(
            root,
            "class Conta\n+ saldo: double\n+ total(): double\nclass Vazia\n",
        )

        session.handle("class Conta\n+ total(): int\nclass Vazia\n+ x: int\n")

        members = {
            member.name: member.type_name
            for member in session._contract.units[0].members
        }
        self.assertEqual({"saldo": "double", "total": "int"}, members)
        self.assertIs(ContractStatus.TRUSTED, classify(session._contract))

    def test_correction_preserves_relationships_it_does_not_address(self) -> None:
        root = self._root()
        session, _project, _model = self._session(
            root,
            "class A\nclass B\n+ x: int\nclass C\n+ y: int\n"
            "class D\n+ z: int\nclass Vazia\nA <|-- B\nC <|-- D\n",
        )

        session.handle(
            "class A\nclass B\n+ x: int\n+ q: int\nA <|-- B\n"
            "class Vazia\n+ w: int\n"
        )

        pairs = {
            (relationship.parent, relationship.child)
            for relationship in session._contract.relationships
        }
        self.assertIn(("A", "B"), pairs)
        self.assertIn(("C", "D"), pairs)

    def test_user_rule_supersedes_pdf_rule_for_the_same_scope(self) -> None:
        root = self._root()
        session, _project, _model = self._session(
            root,
            "class Conta\n+ total(): double\nO total aumenta em 15%.\n"
            "class Vazia\n",
            source="ocr",
        )

        session.handle(
            "class Conta\n+ total(): double\nO total aumenta em 25%.\n"
            "class Vazia\n+ x: int\n"
        )

        factors = {
            rule.value
            for rule in extract_rules(session._contract)
            if rule.kind == "factor"
        }
        self.assertEqual({1.25}, factors)

    def test_correction_keeps_other_relationship_kinds_for_the_child(self) -> None:
        root = self._root()
        session, _project, _model = self._session(
            root,
            "class I\n+ run(): void\nclass B implements I\n+ x: int\n"
            "class A\n+ a: int\nclass Vazia\nA <|-- B\n",
        )

        session.handle(
            "class A\n+ a: int\nclass B\n+ x: int\n+ q: int\nA <|-- B\n"
            "class Vazia\n+ w: int\n"
        )

        relationships = {
            (relationship.parent, relationship.child, relationship.kind)
            for relationship in session._contract.relationships
        }
        self.assertIn(("I", "B", "implements"), relationships)
        self.assertIn(("A", "B", "inheritance"), relationships)

    def test_correction_does_not_merge_overloads_by_name_only(self) -> None:
        root = self._root()
        session, _project, _model = self._session(
            root,
            "class Conta\n+ total(x: int): double\n"
            "+ total(x: double): double\nclass Vazia\n",
        )

        session.handle(
            "class Conta\n+ total(x: int): int\n"
            "+ total(x: double): double\nclass Vazia\n+ y: int\n"
        )

        signatures = {
            (tuple(type_name for _, type_name in member.parameters), member.type_name)
            for member in session._contract.units[0].members
            if member.name == "total"
        }
        self.assertEqual(
            {(("int",), "int"), (("double",), "double")}, signatures
        )

    def test_line_by_line_correction_is_applied_on_empty_line(self) -> None:
        root = self._root()
        session, _project, _model = self._session(root, "class Conta\n")

        first = session.handle("class Conta")
        self.assertIn("linha vazia", first.text)
        session.handle("+ total(): double")
        applied = session.handle("")

        self.assertIn("Agora posso gerar", applied.text)
        self.assertIs(ContractStatus.TRUSTED, classify(session._contract))
        self.assertEqual(
            ["total"], [member.name for member in session._contract.units[0].members]
        )

    def test_chat_run_java_success_is_labeled_as_smoke_test(self) -> None:
        root = self._root()
        project = root / "projeto"
        project.mkdir()
        template = root / "criterios.md"
        template.write_text("Java POO.\n", encoding="utf-8")
        model = CountingModel(
            ['<run_java main_class="App" />', "<respond>Feito.</respond>"]
        )
        session = AssistantSession(
            config=AppConfig(project, root / "data", root / "config", root / "state"),
            model=model,
            pdf_extractor=FixedExtractor("Enunciado sem classes.\n"),
            toolchain=OkToolchain(),
            criteria_template=template,
            profile=profile_for(root),
        )
        self.addCleanup(session.close)

        reply = session.handle("Execute App")

        self.assertIn("smoke test", reply.text)
        self.assertTrue(
            any("smoke test" in item for item in session.evidence.locally_tested)
        )
        self.assertTrue(
            any("smoke test" in item for item in session.evidence.observations)
        )


if __name__ == "__main__":
    unittest.main()
