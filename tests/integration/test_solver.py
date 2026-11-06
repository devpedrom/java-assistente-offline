from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from java_assistant.adapters.base import CompileResult, RunResult
from java_assistant.adapters.java8 import Java8Adapter
from java_assistant.adapters.stub import StubAdapter
from java_assistant.core.budget import ContextBudget
from java_assistant.core.solver import Solver
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.core.spec import Member, Requirement, Relationship, Specification, Unit
from java_assistant.model.client import Message
from java_assistant.pdf.extract import PdfEvidence
from java_assistant.profile import DEFAULT_SECTIONS
from java_assistant.review.report import EvidenceReport
from java_assistant.uml.extract import UmlExtractor
from java_assistant.workspace.files import Workspace
from java_assistant.workspace.history import History


def unit(name: str, *, main: bool = False, confidence: float = 1.0) -> Unit:
    member = (
        Member("main", "method", "void", "public", modifiers=("static",))
        if main
        else Member("total", "method", "double", "public")
    )
    return Unit(name, "class", (member,), confidence=confidence)


def trusted(
    *units: Unit, relationships: tuple[Relationship, ...] = ()
) -> Specification:
    return Specification(
        units,
        relationships,
        (Requirement("Preserve os nomes do contrato.", "pdf-text", 0.98),),
    )


class FakeModel:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[list[Message]] = []

    def complete(self, messages: list[Message]):
        self.calls.append(list(messages))
        if not self.replies:
            raise AssertionError("chamada ao modelo sem resposta preparada")
        from java_assistant.model.client import ModelReply

        return ModelReply(self.replies.pop(0))


class FakeStore:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def remember(self, kind: str, content: str) -> None:
        self.events.append((kind, content))


class FakeToolchain:
    def __init__(
        self, *, diagnostics: str = "", run_ok: bool = True, run_outputs: list[str] | None = None
    ) -> None:
        self.diagnostics = diagnostics
        self.run_ok = run_ok
        self.run_outputs = list(run_outputs or [])
        self.compiled: list[list[Path]] = []
        self.runs: list[str] = []

    def compile(self, sources, timeout_s: int = 30) -> CompileResult:
        self.compiled.append(list(sources))
        return CompileResult(
            not self.diagnostics, self.diagnostics, Path.cwd(), ("fake",)
        )

    def run(
        self, main_class: str, timeout_s: int, args=(), stdin: str = "", jvm_args=()
    ) -> RunResult:
        self.runs.append(main_class)
        if self.run_outputs:
            if len(self.run_outputs) > 1:
                return RunResult(True, self.run_outputs.pop(0), "", 0, False)
            return RunResult(True, self.run_outputs[0], "", 0, False)
        if self.run_ok:
            return RunResult(True, "saida", "", 0, False)
        return RunResult(False, "", "erro de execucao", 1, False)

    def inspect(self, symbol: str, timeout_s: int = 10) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, "", "")


class RecordingAdapter(StubAdapter):
    def __init__(
        self,
        *,
        repair: str | None = None,
        entry: str | None = None,
        structural: tuple[tuple[str, ...], ...] = (),
    ) -> None:
        self.repair = repair
        self.entry = entry
        self.structural = list(structural)

    def repair_target(self, diagnostics: str) -> str | None:
        return self.repair

    def entry_point(self, spec: Specification) -> str | None:
        return self.entry

    def structural_issues(self, spec, toolchain) -> tuple[str, ...]:
        return self.structural.pop(0) if self.structural else ()


class JavaPromptAdapter(Java8Adapter):
    def structural_issues(self, spec, toolchain) -> tuple[str, ...]:
        return ()


class SolverTests(unittest.TestCase):


    def test_last_repair_is_evaluated_when_budget_ends_midway_through_targets(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            class SharedDependencyCheck(FakeToolchain):
                def run(self, main_class, timeout_s, args=(), stdin="", jvm_args=()):
                    if main_class != "Validador":
                        return super().run(main_class, timeout_s, args, stdin, jvm_args)
                    output = ("✔ Conta A\n✔ Saldo B" if (root/"Conta.txt").read_text() == "FIXED\n"
                              else "❌ Conta A\n❌ Saldo B")
                    return RunResult(True, output, "", 0, False)
            solver, _, _, evidence = self._solver(
                root, trusted(unit("Conta"), unit("Saldo")),
                replies=["OLD", "UNCHANGED", "FIXED"], toolchain=SharedDependencyCheck(),
                checkers=("Validador",), repair_attempts=1,
            )
            outcome = solver.run("resolva")
            self.assertTrue(outcome.completed, outcome.text)
            self.assertEqual("FIXED\n", (root/"Conta.txt").read_text())
            self.assertTrue(any("Validador" in line for line in evidence.locally_tested))



    def test_context_overflow_during_repair_still_restores_the_best_candidate(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            solver, _, _, evidence = self._solver(
                root, trusted(unit("Conta")), replies=["BEST", "WORSE"],
                toolchain=FakeToolchain(run_outputs=[
                    "✔ Conta one\n❌ Conta two", "❌ Conta " + "x" * 20000,
                    "✔ Conta one\n❌ Conta two",
                ]), checkers=("Validador",), repair_attempts=2,
            )
            outcome = solver.run("resolva")
            self.assertFalse(outcome.completed)
            self.assertEqual("BEST\n", (root/"Conta.txt").read_text())
            self.assertTrue(any("restaur" in text for text in evidence.observations))

    def test_best_current_candidate_does_not_keep_an_obsolete_checker_pass(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            class Checks(FakeToolchain):
                def run(self, main_class, timeout_s, args=(), stdin="", jvm_args=()):
                    old = (root/"Conta.txt").read_text() == "OLD\n"
                    if main_class == "First":
                        output = "✔ Conta A" if old else "❌ Conta A"
                    else:
                        output = ("❌ Conta B\n❌ Conta C\n❌ Conta D" if old
                                  else "✔ Conta B\n✔ Conta C\n❌ Conta D")
                    return RunResult(True, output, "", 0, False)
            solver, _, _, evidence = self._solver(
                root, trusted(unit("Conta")), replies=["OLD", "NEW"],
                toolchain=Checks(), checkers=("First", "Second"), repair_attempts=1,
            )
            outcome = solver.run("resolva")
            self.assertFalse(outcome.completed)
            self.assertEqual("NEW\n", (root/"Conta.txt").read_text())
            self.assertEqual([], evidence.locally_tested)

    def test_later_checker_cannot_silently_regress_an_earlier_checker(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)

            class DependentChecks(FakeToolchain):
                def run(self, main_class, timeout_s, args=(), stdin="", jvm_args=()):
                    first = (root/"Conta.txt").read_text() == "GOOD\n"
                    second = (root/"Saldo.txt").read_text() == "BAD\n"
                    ok = first and not second if main_class == "CheckOne" else second
                    name = "Conta" if main_class == "CheckOne" else "Saldo"
                    return RunResult(True, ("✔" if ok else "❌") + " " + name, "", 0, False)

            solver, _, _, evidence = self._solver(
                root, trusted(unit("Conta"), unit("Saldo")),
                replies=["INITIAL", "OLD", "GOOD", "BAD"],
                toolchain=DependentChecks(), checkers=("CheckOne", "CheckTwo"),
                repair_attempts=2,
            )
            outcome = solver.run("resolva")
            self.assertFalse(outcome.completed)
            self.assertEqual("GOOD\n", (root/"Conta.txt").read_text())
            self.assertEqual("OLD\n", (root/"Saldo.txt").read_text())
            self.assertEqual([], evidence.locally_tested)

    @unittest.skipUnless(shutil.which("javac") and shutil.which("javap"), "JDK indisponível")
    def test_restored_candidate_is_the_one_executed_by_real_java(self) -> None:
        class Utf8Toolchain(JavaToolchain):
            def run(self, main_class, timeout_s, args=(), stdin="", jvm_args=()):
                return super().run(main_class, timeout_s, args, stdin,
                                   ("-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", *jvm_args))

        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root/"Validador.java").write_text(
                'public class Validador { public static void main(String[] args) {'
                'double n = new Conta().total();'
                'for (int i=1;i<=3;i++) System.out.println('
                '(n>=i ? "✔" : "❌") + " Conta caso " + i); }}', encoding="utf-8"
            )
            toolchain = Utf8Toolchain(root)
            solver, _, _, evidence = self._solver(
                root, trusted(unit("Conta")),
                replies=["public class Conta { public double total(){return 2;} }",
                         "public class Conta { public double total(){return 1;} }"],
                adapter=Java8Adapter(), toolchain=toolchain,
                checkers=("Validador",), repair_attempts=1,
            )
            outcome = solver.run("resolva")
            result = toolchain.run("Validador", 15)
            self.assertFalse(outcome.completed)
            self.assertEqual("✔ Conta caso 1\n✔ Conta caso 2\n❌ Conta caso 3\n", result.stdout)
            self.assertTrue(any("restaur" in text for text in evidence.observations))

    def test_checker_regression_restores_and_revalidates_the_best_sources(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            solver, _, toolchain, evidence = self._solver(
                root, trusted(unit("Conta")), replies=["BEST", "WORSE"],
                toolchain=FakeToolchain(run_outputs=[
                    "✔ Conta caso A\n✔ Conta caso B\n❌ Conta caso C",
                    "✔ Conta caso A\n❌ Conta caso B\n❌ Conta caso C",
                    "✔ Conta caso A\n✔ Conta caso B\n❌ Conta caso C",
                ]), checkers=("Validador",), repair_attempts=1,
            )
            outcome = solver.run("resolva")
            self.assertEqual("BEST\n", (root/"Conta.txt").read_text(encoding="utf-8"))
            self.assertFalse(outcome.completed)
            self.assertEqual(3, len(toolchain.compiled))
            self.assertEqual(3, len(toolchain.runs))
            self.assertIn("❌ Conta caso C", outcome.text)
            self.assertNotIn("❌ Conta caso B", outcome.text)
            self.assertTrue(any("restaur" in item for item in evidence.observations))
            self.assertTrue(any(solver.workspace.current_hash(Path("Conta.txt")) in item
                                for item in evidence.compiled))

    def test_checker_equal_scores_keep_the_first_candidate(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            solver, _, _, _ = self._solver(
                root, trusted(unit("Conta")), replies=["FIRST", "SECOND"],
                toolchain=FakeToolchain(run_outputs=["✔ Conta A\n❌ Conta B"]),
                checkers=("Validador",), repair_attempts=1,
            )
            outcome = solver.run("resolva")
            self.assertFalse(outcome.completed)
            self.assertEqual("FIRST\n", (root/"Conta.txt").read_text(encoding="utf-8"))

    def test_rule_after_the_pdf_excerpt_limit_reaches_the_protected_section(self) -> None:
        preamble = "Instrucoes gerais sem classe. " * 120
        statement = (
            preamble
            + "\nclass Conta\n+ total(): double\n"
            "Regra confirmada da unidade: preserve a formula do enunciado.\n"
        )
        spec = UmlExtractor().extract(PdfEvidence(statement, "text", ()))
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                spec,
                replies=[
                    "public class Conta { public double total() { return 1.0; } }"
                ],
                adapter=JavaPromptAdapter(),
            )
            solver.pdf_text = statement

            outcome = solver.run("crie Conta")

        self.assertTrue(outcome.completed, outcome.text)
        system = model.calls[0][0].content
        self.assertIn("Regra confirmada da unidade", system)
        self.assertIn("[pdf-text | Conta]", system)
        self.assertIn("public double total();", system)

    def _solver(
        self,
        root: Path,
        spec: Specification,
        *,
        replies: list[str],
        adapter=None,
        toolchain=None,
        repair_attempts: int = 2,
        max_files: int = 40,
        checkers: tuple[str, ...] = (),
        evidence: EvidenceReport | None = None,
    ):
        workspace = Workspace(root)
        model = FakeModel(replies)
        toolchain = toolchain or FakeToolchain()
        evidence = evidence or EvidenceReport()
        solver = Solver(
            spec=spec,
            adapter=adapter or StubAdapter(),
            toolchain=toolchain,
            model=model,
            workspace=workspace,
            history=History(workspace),
            store=FakeStore(),
            evidence=evidence,
            budget=ContextBudget(),
            criteria="criterios",
            pdf_text="",
            memory_summary="",
            repair_attempts=repair_attempts,
            max_files=max_files,
            checkers=checkers,
        )
        return solver, model, toolchain, evidence

    def test_no_contract_asks_for_confirmation_without_model_call_or_compile(
        self,
    ) -> None:
        with TemporaryDirectory() as temp:
            solver, model, toolchain, evidence = self._solver(
                Path(temp), Specification((), (), ()), replies=[]
            )

            outcome = solver.run("resolva")

        self.assertFalse(outcome.completed)
        self.assertIn("Não há contrato confiável", outcome.text)
        self.assertEqual([], model.calls)
        self.assertEqual([], toolchain.compiled)
        self.assertTrue(evidence.observations)

    def test_trusted_contract_generates_in_dependency_order_and_compiles(self) -> None:
        spec = trusted(
            unit("Child"),
            unit("Base"),
            relationships=(Relationship("Base", "Child", "inheritance", 0.98),),
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            solver, model, toolchain, evidence = self._solver(
                root, spec, replies=["BASE", "CHILD"]
            )

            outcome = solver.run("crie as classes")

            self.assertTrue(outcome.completed)
            self.assertEqual("BASE\n", (root / "Base.txt").read_text(encoding="utf-8"))
            self.assertEqual("CHILD\n", (root / "Child.txt").read_text(encoding="utf-8"))

        self.assertEqual(2, len(model.calls))
        self.assertEqual(
            ["Base.txt", "Child.txt"], [str(source) for source in toolchain.compiled[-1]]
        )
        self.assertIn("Solução concluída", outcome.text)
        self.assertTrue(any("sha256=" in item for item in evidence.compiled))

    def test_invalid_model_reply_retries_once_with_the_error(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["", "CONTA"],
                adapter=RecordingAdapter(entry=None),
            )

            outcome = solver.run("crie Conta")

        self.assertTrue(outcome.completed)
        self.assertEqual(2, len(model.calls))
        self.assertIn("rejeitada", model.calls[1][-1].content)

    def test_confirmed_entry_must_belong_to_the_plan(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, toolchain, _ = self._solver(
                Path(temp),
                trusted(unit("App", main=True)),
                replies=["APP"],
                adapter=RecordingAdapter(entry=None),
            )

            outcome = solver.run("crie App", confirmed_entry="Nope")

        self.assertFalse(outcome.completed)
        self.assertIn("Nope", outcome.text)
        self.assertEqual([], toolchain.runs)
        self.assertEqual([], model.calls)

    def test_confirmed_entry_resolves_ambiguous_main(self) -> None:
        with TemporaryDirectory() as temp:
            solver, _, toolchain, _ = self._solver(
                Path(temp),
                trusted(unit("App", main=True), unit("Zapp", main=True)),
                replies=["APP", "ZAPP"],
                adapter=RecordingAdapter(entry=None),
            )

            outcome = solver.run("crie as classes", confirmed_entry="App")

        self.assertTrue(outcome.completed)
        self.assertEqual(["App"], toolchain.runs)

    def test_repeated_runs_do_not_duplicate_evidence(self) -> None:
        with TemporaryDirectory() as temp:
            solver, _, _, evidence = self._solver(
                Path(temp), trusted(unit("Conta")), replies=["A", "B"]
            )

            self.assertTrue(solver.run("primeiro").completed)
            self.assertTrue(solver.run("segundo").completed)

        self.assertEqual(1, len(evidence.compiled))
        self.assertEqual(len(evidence.unproven), len(set(evidence.unproven)))
        self.assertEqual(len(evidence.locally_tested), len(set(evidence.locally_tested)))

    def test_truncated_context_is_recorded_in_the_report(self) -> None:
        with TemporaryDirectory() as temp:
            solver, _, _, evidence = self._solver(
                Path(temp), trusted(unit("Conta")), replies=["CONTA"]
            )
            solver.budget = ContextBudget(
                sections={**dict(DEFAULT_SECTIONS), "memory": 1}
            )
            solver.memory_summary = "linha antiga\n" * 20

            outcome = solver.run("crie Conta")

        self.assertTrue(outcome.completed)
        self.assertTrue(any("memory" in note for note in evidence.context_omitted))
        self.assertIn("memory", evidence.render())

    def test_foreign_file_diagnostic_is_reported_and_never_rewritten(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            foreign = root / "Foreign.txt"
            foreign.write_text("ORIGINAL\n", encoding="utf-8")
            solver, model, _, _ = self._solver(
                root,
                trusted(unit("Conta")),
                replies=["CONTA"],
                adapter=RecordingAdapter(repair="Foreign"),
                toolchain=FakeToolchain(diagnostics="Foreign.txt:1: error: boom"),
            )

            outcome = solver.run("crie Conta")

            self.assertFalse(outcome.completed)
            self.assertIn("Foreign", outcome.text)
            self.assertEqual("ORIGINAL\n", foreign.read_text(encoding="utf-8"))

        self.assertEqual(1, len(model.calls))

    def test_repair_is_bounded_by_repair_attempts(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, toolchain, _ = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["A", "B", "C", "D"],
                adapter=RecordingAdapter(repair="Conta"),
                toolchain=FakeToolchain(diagnostics="Conta.txt:1: error: boom"),
                repair_attempts=2,
            )

            outcome = solver.run("crie Conta")

        self.assertFalse(outcome.completed)
        self.assertIn("Conta", outcome.text)
        self.assertEqual(3, len(model.calls))
        self.assertEqual(3, len(toolchain.compiled))

    def test_more_units_than_max_files_fails_before_model_call(self) -> None:
        spec = trusted(unit("A"), unit("B"), unit("C"), unit("D"))
        with TemporaryDirectory() as temp:
            solver, model, toolchain, _ = self._solver(
                Path(temp), spec, replies=[], max_files=3
            )

            outcome = solver.run("resolva")

        self.assertFalse(outcome.completed)
        self.assertIn("3", outcome.text)
        self.assertEqual([], model.calls)
        self.assertEqual([], toolchain.compiled)

    def test_successful_execution_without_a_case_is_a_smoke_test(self) -> None:
        with TemporaryDirectory() as temp:
            solver, _, toolchain, evidence = self._solver(
                Path(temp),
                trusted(unit("App", main=True)),
                replies=["APP"],
                adapter=RecordingAdapter(entry="App"),
            )

            outcome = solver.run("crie App")

        self.assertTrue(outcome.completed)
        self.assertEqual(["App"], toolchain.runs)
        self.assertIn("smoke test", outcome.text)
        self.assertTrue(evidence.locally_tested)
        self.assertTrue(
            all("smoke test" in item for item in evidence.locally_tested)
        )
        self.assertTrue(
            any("entrada/saída" in item.casefold() for item in evidence.observations)
        )

    def test_completion_requires_execution_when_entry_exists(self) -> None:
        with TemporaryDirectory() as temp:
            solver, _, toolchain, _ = self._solver(
                Path(temp),
                trusted(unit("App", main=True)),
                replies=["APP"],
                adapter=RecordingAdapter(entry="App"),
                toolchain=FakeToolchain(run_ok=False),
            )

            outcome = solver.run("crie App")

        self.assertFalse(outcome.completed)
        self.assertIn("erro de execucao", outcome.text)
        self.assertEqual(["App"], toolchain.runs)

    def test_structural_issue_repairs_once_then_completes(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, toolchain, _ = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["A", "B"],
                adapter=RecordingAdapter(
                    structural=(("Conta: falta o membro total.",), ())
                ),
            )

            outcome = solver.run("crie Conta")

        self.assertTrue(outcome.completed)
        self.assertEqual(2, len(model.calls))
        self.assertEqual(2, len(toolchain.compiled))

    def test_local_checker_feedback_regenerates_the_failing_unit(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, toolchain, evidence = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["A", "B"],
                toolchain=FakeToolchain(
                    run_outputs=[
                        "❌ Conta total() = 2.0 | esperado 3.0",
                        "✔ Conta total() = 3.0",
                    ]
                ),
                checkers=("Validador",),
            )

            outcome = solver.run("resolva")

        self.assertTrue(outcome.completed, outcome.text)
        self.assertEqual(2, len(model.calls))
        self.assertIn("esperado 3.0", model.calls[1][-1].content)
        self.assertEqual(["Validador", "Validador"], toolchain.runs[:2])
        self.assertTrue(any("Validador" in item for item in evidence.locally_tested))
        self.assertIn("verificador local", outcome.text)

    def test_local_checker_repair_restates_the_extracted_rule(self) -> None:
        caixa = Unit(
            "Caixa",
            "class",
            (
                Member("saldo", "field", "double", "private"),
                Member(
                    "calcular",
                    "method",
                    "double",
                    "public",
                    (("quantidade", "int"),),
                ),
            ),
        )
        spec = Specification(
            (caixa,),
            (),
            (
                Requirement(
                    "calcular: o saldo aumenta em 50%.", "pdf-text", 0.98, "Caixa"
                ),
            ),
        )
        bad = (
            "public class Caixa { private double saldo; "
            "public double calcular(int quantidade) { return quantidade * 1.5; } }"
        )
        good = (
            "public class Caixa { private double saldo; "
            "public double calcular(int quantidade) { return saldo * 1.5; } }"
        )
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                spec,
                replies=[bad, bad, good],
                toolchain=FakeToolchain(
                    run_outputs=[
                        "❌ Caixa calcular() = 1.5 | esperado 900.0",
                        "✔ Caixa calcular() = 900.0",
                    ]
                ),
                checkers=("Validador",),
                repair_attempts=1,
            )

            outcome = solver.run("resolva")

        self.assertTrue(outcome.completed, outcome.text)
        self.assertEqual(3, len(model.calls))
        repair = model.calls[2][-1].content
        self.assertIn("REGRAS DO ENUNCIADO", repair)
        self.assertIn("multiplicar saldo", repair)
        self.assertIn("esperado 900.0", repair)

    def test_local_checker_failure_is_reported_after_bounded_repairs(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["A", "B"],
                toolchain=FakeToolchain(run_outputs=["✘ Conta total() = 1.0"]),
                checkers=("Validador",),
                repair_attempts=1,
            )

            outcome = solver.run("resolva")

        self.assertFalse(outcome.completed)
        self.assertIn("✘ Conta total() = 1.0", outcome.text)
        self.assertEqual(2, len(model.calls))

    def test_local_checker_limits_the_textual_gate_to_one_correction(self) -> None:
        spec = Specification(
            (unit("Conta"),),
            (),
            (Requirement("O total dobra.", "pdf-text", 0.98, "Conta"),),
        )
        with TemporaryDirectory() as temp:
            solver, model, _, evidence = self._solver(
                Path(temp),
                spec,
                replies=["CONTA", "CONTA"],
                toolchain=FakeToolchain(run_outputs=["✔ Conta total() = 2.0"]),
                checkers=("Validador",),
            )

            outcome = solver.run("resolva")

        self.assertTrue(outcome.completed, outcome.text)
        self.assertEqual(2, len(model.calls))
        self.assertTrue(
            any("verificador local decidirá" in item for item in evidence.unproven)
        )

    def test_textual_rule_gate_still_blocks_without_a_checker(self) -> None:
        spec = Specification(
            (unit("Conta"),),
            (),
            (Requirement("O total dobra.", "pdf-text", 0.98, "Conta"),),
        )
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                spec,
                replies=["CONTA", "CONTA"],
                adapter=RecordingAdapter(entry=None),
            )

            outcome = solver.run("resolva")

        self.assertFalse(outcome.completed)
        self.assertIn("multiplicar", outcome.text)
        self.assertIn("2.0", outcome.text)
        self.assertEqual(2, len(model.calls))

    def test_local_checker_section_header_points_to_the_unit(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["A", "B"],
                toolchain=FakeToolchain(
                    run_outputs=[
                        "── Conta.total() [base 300] ──\n❌ total() = 2.0 | 3.0",
                        "── Conta.total() [base 300] ──\n✔ total() = 3.0",
                    ]
                ),
                checkers=("Validador",),
            )

            outcome = solver.run("resolva")

        self.assertTrue(outcome.completed, outcome.text)
        self.assertIn("total() = 2.0", model.calls[1][-1].content)

    def test_local_checker_maps_a_nameless_failure_to_the_previous_unit(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["A", "B"],
                toolchain=FakeToolchain(
                    run_outputs=[
                        "  ✔  Conta autonomia() = 500.00 km | ok\n"
                        "  ── Limite inválido ──\n"
                        "  ❌ FALHA: exceção não lançada!",
                        "  ✔  Conta autonomia() = 500.00 km | ok",
                    ]
                ),
                checkers=("Validador",),
            )

            outcome = solver.run("resolva")

        self.assertTrue(outcome.completed, outcome.text)
        self.assertIn("exceção", model.calls[1][-1].content)

    def test_checker_repairs_every_failing_unit_in_one_round(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                trusted(unit("Conta"), unit("Saldo")),
                replies=["A", "B", "C", "D"],
                toolchain=FakeToolchain(
                    run_outputs=[
                        "── Conta.total() ──\n❌ total() = 1.0 | 2.0\n"
                        "── Saldo.total() ──\n❌ total() = 1.0 | 2.0",
                        "✔ tudo certo",
                    ]
                ),
                checkers=("Validador",),
            )

            outcome = solver.run("resolva")

        self.assertTrue(outcome.completed, outcome.text)
        self.assertEqual(4, len(model.calls))

    def test_local_checker_that_cannot_run_is_not_reported_as_approved(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["A"],
                toolchain=FakeToolchain(run_ok=False),
                checkers=("Validador",),
            )

            outcome = solver.run("resolva")

        self.assertFalse(outcome.completed)
        self.assertIn("não terminou com sucesso", outcome.text)
        self.assertEqual(1, len(model.calls))

    def test_local_checker_without_conference_lines_is_not_approved(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["A"],
                toolchain=FakeToolchain(run_outputs=["nada a conferir"]),
                checkers=("Validador",),
            )

            outcome = solver.run("resolva")

        self.assertFalse(outcome.completed)
        self.assertIn("nenhuma linha", outcome.text)
        self.assertEqual(1, len(model.calls))

    def test_repair_prompt_includes_the_current_file(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["A", "B", "C"],
                adapter=RecordingAdapter(repair="Conta"),
                toolchain=FakeToolchain(diagnostics="Conta.txt:1: error: boom"),
            )

            outcome = solver.run("crie Conta")

        self.assertFalse(outcome.completed)
        self.assertIn("ARQUIVO ATUAL", model.calls[1][-1].content)

    def test_constructor_mismatch_shows_the_parent_signature(self) -> None:
        base = Unit(
            "Base",
            "class",
            (
                Member(
                    "Base",
                    "constructor",
                    "Base",
                    "public",
                    (("id", "int"), ("ativo", "boolean")),
                ),
            ),
        )
        child = Unit(
            "Conta",
            "class",
            (
                Member(
                    "Conta",
                    "constructor",
                    "Conta",
                    "public",
                    (("id", "int"), ("ativo", "boolean")),
                ),
            ),
        )
        spec = trusted(
            base,
            child,
            relationships=(Relationship("Base", "Conta", "inheritance", 1.0),),
        )
        diagnostic = (
            "Conta.java:5: error: no suitable constructor found for Base(int)"
        )
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                spec,
                replies=["A", "B", "C"],
                adapter=RecordingAdapter(repair="Conta"),
                toolchain=FakeToolchain(diagnostics=diagnostic),
                repair_attempts=1,
            )

            solver.run("crie Conta")

        self.assertIn("super(id, ativo)", model.calls[2][-1].content)

    def test_generation_prompt_shows_the_parent_constructor_order(self) -> None:
        base = Unit(
            "Base",
            "class",
            (
                Member(
                    "Base",
                    "constructor",
                    "Base",
                    "public",
                    (("nome", "String"), ("salario", "Double"), ("registro", "int")),
                ),
            ),
        )
        child = Unit(
            "Conta",
            "class",
            (
                Member(
                    "Conta",
                    "constructor",
                    "Conta",
                    "public",
                    (
                        ("registro", "int"),
                        ("cargo", "String"),
                        ("nome", "String"),
                        ("salario", "Double"),
                    ),
                ),
            ),
        )
        spec = trusted(
            base,
            child,
            relationships=(Relationship("Base", "Conta", "inheritance", 1.0),),
        )
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                spec,
                replies=[
                    "public class Base {}",
                    "public class Conta {}",
                ],
                adapter=JavaPromptAdapter(),
                toolchain=FakeToolchain(),
            )

            solver.run("crie Conta")

        system = next(
            message.content
            for message in model.calls[1]
            if "CONSTRUTOR DA SUPERCLASSE" in message.content
        )
        self.assertIn("super(nome, salario, registro)", system)

    def test_parent_arguments_use_field_names_when_javap_hides_them(self) -> None:
        base = Unit(
            "Base",
            "class",
            (
                Member("nome", "field", "String", "private"),
                Member("salario", "field", "Double", "private"),
                Member("registro", "field", "int", "private"),
                Member(
                    "Base",
                    "constructor",
                    "Base",
                    "public",
                    (("arg1", "String"), ("arg2", "Double"), ("arg3", "int")),
                ),
            ),
        )
        child = Unit(
            "Conta",
            "class",
            (
                Member(
                    "Conta",
                    "constructor",
                    "Conta",
                    "public",
                    (
                        ("arg1", "int"),
                        ("arg2", "String"),
                        ("arg3", "String"),
                        ("arg4", "Double"),
                    ),
                ),
            ),
        )
        spec = trusted(
            base,
            child,
            relationships=(Relationship("Base", "Conta", "inheritance", 1.0),),
        )
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                spec,
                replies=[
                    "public class Base {}",
                    "public class Conta {}",
                ],
                adapter=JavaPromptAdapter(),
                toolchain=FakeToolchain(),
            )

            solver.run("crie Conta")

        system = next(
            message.content
            for message in model.calls[1]
            if "CONSTRUTOR DA SUPERCLASSE" in message.content
        )
        self.assertIn("super(nome, salario, registro)", system)
        self.assertNotIn("super(arg1, arg2, arg3)", system)

    def test_generation_shows_sources_of_referenced_types(self) -> None:
        saldo = Unit(
            "Saldo",
            "class",
            (Member("total", "field", "Double", "private"),),
        )
        conta = Unit(
            "Conta",
            "class",
            (Member("saldo", "field", "Saldo", "private"),),
        )
        spec = trusted(saldo, conta)
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                spec,
                replies=[
                    "public class Saldo {}",
                    "public class Conta {}",
                ],
                adapter=JavaPromptAdapter(),
                toolchain=FakeToolchain(),
            )

            solver.run("crie Conta e Saldo")

        system = "\n".join(
            message.content for message in model.calls[1]
        )
        self.assertIn("ARQUIVO: Saldo.java", system)
        self.assertIn("public class Saldo {}", system)

    def test_rewrite_prompt_drops_the_old_file(self) -> None:
        spec = trusted(unit("Conta"))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            solver, _, _, _ = self._solver(root, spec, replies=[])
            (root / f"Conta{solver.adapter.source_extension}").write_text(
                "conteudo", encoding="utf-8"
            )

            keep = solver._unit_prompt(spec.units[0], "crie", (), "erro", True)
            fresh = solver._unit_prompt(spec.units[0], "crie", (), "erro", False)

        self.assertIn("ARQUIVO ATUAL", keep[-1].content)
        self.assertNotIn("ARQUIVO ATUAL", fresh[-1].content)
        self.assertIn("Reescreva o arquivo do zero", fresh[-1].content)

    def test_repeated_compile_repairs_drop_the_old_file(self) -> None:
        with TemporaryDirectory() as temp:
            solver, model, _, _ = self._solver(
                Path(temp),
                trusted(unit("Conta")),
                replies=["A", "B", "C"],
                adapter=RecordingAdapter(repair="Conta"),
                toolchain=FakeToolchain(diagnostics="Conta.txt:1: error: boom"),
                repair_attempts=2,
            )

            outcome = solver.run("crie Conta")

        self.assertFalse(outcome.completed)
        self.assertIn("ARQUIVO ATUAL", model.calls[1][-1].content)
        self.assertNotIn("ARQUIVO ATUAL", model.calls[2][-1].content)
        self.assertIn("Reescreva o arquivo do zero", model.calls[2][-1].content)

    def test_two_runs_produce_identical_evidence_and_hashes(self) -> None:
        spec = trusted(
            unit("Base"),
            unit("Child"),
            relationships=(Relationship("Base", "Child", "inheritance", 0.98),),
        )
        reports = []
        for _ in range(2):
            with TemporaryDirectory() as temp:
                solver, _, _, evidence = self._solver(
                    Path(temp), spec, replies=["BASE", "CHILD"]
                )
                self.assertTrue(solver.run("crie").completed)
                reports.append(evidence.render())

        self.assertEqual(reports[0], reports[1])


class ReportTests(unittest.TestCase):
    def test_report_separates_omitted_context_and_observations(self) -> None:
        report = EvidenceReport(
            confirmed_pdf=["classe A"],
            inferred_uml=["A herda de B"],
            compiled=["A.java sha256=abc"],
            locally_tested=["java App: código 0"],
            unproven=["regra de negócio"],
            context_omitted=["memory: omitida"],
            observations=["Foreign.java não foi gerado pelo assistente"],
        )

        text = report.render()

        for title in (
            "Confirmado pelo PDF",
            "Inferido do UML",
            "Compilado",
            "Testado localmente",
            "Não comprovado",
            "Contexto omitido (limite de tokens)",
            "Observações de verificação",
        ):
            self.assertIn(f"## {title}", text)
        self.assertIn("- memory: omitida", text)
        self.assertIn("- Foreign.java não foi gerado pelo assistente", text)


if __name__ == "__main__":
    unittest.main()
