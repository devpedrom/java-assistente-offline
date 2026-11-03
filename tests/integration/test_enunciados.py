"""Five distinct statements solved end-to-end through the staged solver.

O cenário "composicao" usa um campo tipado (`Time.capitao: Jogador`), pois o
extrator conservador não interpreta setas de composição/agregação; ele cobre a
dependência por tipo de campo, não a relação explícita.
"""

import json
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
import unittest

from java_assistant.adapters.java8 import Java8Adapter
from java_assistant.core.budget import ContextBudget
from java_assistant.core.solver import Solver, plan
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.memory.store import ProjectStore, project_identifier
from java_assistant.model.client import ModelReply
from java_assistant.pdf.extract import PdfEvidence
from java_assistant.review.report import EvidenceReport
from java_assistant.uml.extract import UmlExtractor
from java_assistant.workspace.files import Workspace
from java_assistant.workspace.history import History


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "enunciados"
SCENARIOS = ("formas", "composicao", "interface", "entrada_saida", "bonus")
MODES = ("feliz", "reparo", "negativo")


class QueuedModel:
    """Answers each unit from its own queue, so order does not matter."""

    def __init__(self, queues: dict[str, list[str]]) -> None:
        self.queues = {name: list(items) for name, items in queues.items()}
        self.prompts: list[list] = []
        self.calls: list[str] = []

    def complete(self, messages):
        self.prompts.append(list(messages))
        name = None
        for message in reversed(messages):
            match = re.search(r"Escreva SOMENTE (\w+)\.java", message.content)
            if match:
                name = match.group(1)
                break
        assert name is not None, messages[-1].content
        self.calls.append(name)
        queue = self.queues.get(name)
        assert queue, f"Sem resposta preparada para {name}."
        return ModelReply(queue.pop(0))


def _projection(spec) -> dict:
    return {
        "units": [
            {
                "name": unit.name,
                "kind": unit.kind,
                "members": [
                    {
                        "name": member.name,
                        "kind": member.kind,
                        "type_name": member.type_name,
                        "visibility": member.visibility,
                        "parameters": [list(parameter) for parameter in member.parameters],
                        "modifiers": list(member.modifiers),
                    }
                    for member in unit.members
                ],
            }
            for unit in spec.units
        ],
        "relationships": [
            {
                "parent": item.parent,
                "child": item.child,
                "kind": item.kind,
            }
            for item in spec.relationships
        ],
    }


def _fixture(name: str) -> tuple[str, dict, dict, dict]:
    base = FIXTURES / name
    return (
        (base / "enunciado.txt").read_text(encoding="utf-8"),
        json.loads((base / "contrato_esperado.json").read_text(encoding="utf-8")),
        json.loads((base / "respostas_modelo.json").read_text(encoding="utf-8")),
        json.loads((base / "casos_execucao.json").read_text(encoding="utf-8")),
    )


@unittest.skipUnless(shutil.which("javac"), "javac indisponível neste ambiente")
class StatementTests(unittest.TestCase):
    def _solve(self, name: str, mode: str):
        text, expected, replies, cases = _fixture(name)
        queues = {unit: list(items) for unit, items in replies["feliz"].items()}
        queues.update(
            {unit: list(items) for unit, items in replies.get(mode, {}).items()}
        )
        spec = UmlExtractor().extract(PdfEvidence(text, "text", ()))
        model = QueuedModel(queues)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        project = root / "projeto"
        project.mkdir()
        workspace = Workspace(project)
        store = ProjectStore.open("sha-" + name, project_identifier(project), root / "state")
        self.addCleanup(store.close)
        toolchain = JavaToolchain(project)
        solver = Solver(
            spec=spec,
            adapter=Java8Adapter(),
            toolchain=toolchain,
            model=model,
            workspace=workspace,
            history=History(workspace),
            store=store,
            evidence=EvidenceReport(),
            budget=ContextBudget(),
            criteria="Critérios de teste: preserve o contrato.",
        )
        evidence = solver.evidence
        return (
            solver.run("Resolva o enunciado."),
            model,
            toolchain,
            spec,
            expected,
            cases,
            replies,
            evidence,
        )

    def test_happy_path_for_each_statement(self) -> None:
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                outcome, model, toolchain, spec, expected, cases, _replies, _evidence = (
                    self._solve(name, "feliz")
                )

                self.assertTrue(outcome.completed, outcome.text)
                self.assertIn("Solução concluída", outcome.text)
                self.assertEqual(expected, _projection(spec))
                self.assertEqual(sorted(plan(spec).order), sorted(model.calls))
                if cases.get("entry"):
                    result = toolchain.run(
                        cases["entry"],
                        15,
                        stdin=cases.get("stdin", ""),
                        args=tuple(cases.get("args", ())),
                    )
                    self.assertTrue(result.success, result.stderr)
                    for fragment in cases.get("stdout_contains", ()):
                        self.assertIn(fragment, result.stdout)

    def test_one_repair_per_statement(self) -> None:
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                outcome, model, _toolchain, _spec, _expected, _cases, replies, _evidence = (
                    self._solve(name, "reparo")
                )
                target = next(iter(replies["reparo"]))

                self.assertTrue(outcome.completed, outcome.text)
                self.assertEqual(2, model.calls.count(target), model.calls)

    def test_negative_path_fails_honestly(self) -> None:
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                outcome, _model, _toolchain, _spec, _expected, _cases, replies, _evidence = (
                    self._solve(name, "negativo")
                )
                target = next(iter(replies["negativo"]))

                self.assertFalse(outcome.completed, outcome.text)
                self.assertNotIn("Solução concluída", outcome.text)
                self.assertIn(target, outcome.text)

    def test_arithmetic_rules_reach_the_model(self) -> None:
        outcome, model, toolchain, spec, _expected, _cases, _replies, _evidence = (
            self._solve("bonus", "feliz")
        )
        self.assertTrue(outcome.completed, outcome.text)
        bonus = next(
            prompt
            for prompt in model.prompts
            if "Escreva SOMENTE Bonus.java" in prompt[-1].content
        )
        system = bonus[0].content
        matchers = Java8Adapter().matchers()
        source = (toolchain.root / "Bonus.java").read_text(encoding="utf-8")

        self.assertIn("salario * 1.5", system)
        self.assertIn("LIMITES OBRIGATÓRIOS", system)
        self.assertTrue(matchers.factor(1.5).search(source), source)
        self.assertTrue(matchers.upper_bound_guard().search(source), source)
        self.assertEqual(("Bonus",), plan(spec).order)

    def test_scanner_without_explicit_input_is_only_a_smoke_test(self) -> None:
        outcome, _model, toolchain, _spec, _expected, cases, _replies, evidence = (
            self._solve("entrada_saida", "feliz")
        )

        self.assertTrue(outcome.completed, outcome.text)
        self.assertIn("smoke test", outcome.text)
        self.assertTrue(evidence.locally_tested)
        self.assertTrue(
            all("smoke test" in item for item in evidence.locally_tested)
        )

        explicit = toolchain.run(
            cases["entry"], 15, stdin=cases.get("stdin", "")
        )
        self.assertTrue(explicit.success, explicit.stderr)
        for fragment in cases.get("stdout_contains", ()):
            self.assertIn(fragment, explicit.stdout)


if __name__ == "__main__":
    unittest.main()
