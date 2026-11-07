from pathlib import Path
import subprocess
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from java_assistant.core.spec import Member, Specification, Unit
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.java.validator import ContractValidator


FIXTURE = Path(__file__).parents[1] / "fixtures" / "java" / "simple"


class JavaToolchainIntegrationTests(unittest.TestCase):
    def test_recompile_and_close_remove_only_owned_class_directories(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            libraries = root / "bibliotecas"
            libraries.mkdir()
            (libraries / "preservar.txt").write_bytes(b"externo")
            source = root / "Main.java"
            source.write_bytes(b'public class Main { public static void main(String[] args){System.out.print("ok");} }')
            toolchain = JavaToolchain(root, classpath=(libraries,))
            first = toolchain.compile([Path("Main.java")])
            self.addCleanup(shutil.rmtree, first.classes_dir, ignore_errors=True)
            second = toolchain.compile([Path("Main.java")])
            self.addCleanup(shutil.rmtree, second.classes_dir, ignore_errors=True)
            self.assertTrue(first.success, first.diagnostics)
            self.assertTrue(second.success, second.diagnostics)
            self.assertFalse(first.classes_dir.exists())
            self.assertEqual("ok", toolchain.run("Main", 3).stdout)
            toolchain.close()
            toolchain.close()
            self.assertFalse(second.classes_dir.exists())
            self.assertTrue(source.is_file())
            self.assertEqual(b"externo", (libraries / "preservar.txt").read_bytes())
            self.assertEqual([], list(root.rglob("*.class")))

    def test_rejects_absolute_source_even_when_it_is_inside_project(self) -> None:
        with self.assertRaisesRegex(ValueError, "relativo"):
            JavaToolchain(FIXTURE).compile([(FIXTURE / "Main.java").resolve()])

    def test_compiles_with_java_8_target_and_runs_formula(self) -> None:
        toolchain = JavaToolchain(FIXTURE)

        compiled = toolchain.compile([Path("Calculadora.java"), Path("Main.java")])
        result = toolchain.run("Main", timeout_s=5)

        self.assertTrue(compiled.success, compiled.diagnostics)
        self.assertIn("--release", compiled.command)
        self.assertIn("8", compiled.command)
        self.assertTrue(result.success, result.stderr)
        self.assertEqual(result.stdout.strip(), "5")

    def test_compile_error_contains_file_and_line(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Invalido.java").write_text(
                "public class Invalido {\n  isto nao compila\n}\n", encoding="utf-8"
            )
            result = JavaToolchain(root).compile([Path("Invalido.java")])

        self.assertFalse(result.success)
        self.assertIn("Invalido.java", result.diagnostics)
        self.assertRegex(result.diagnostics, r"Invalido\.java:\d+")

    def test_validator_checks_contract_signatures(self) -> None:
        contract = Specification(
            units=(
                Unit(
                    name="Calculadora",
                    kind="class",
                    members=(
                        Member("valor", "field", "int", "private"),
                        Member(
                            "Calculadora",
                            "constructor",
                            "Calculadora",
                            "public",
                            (("valor", "int"),),
                        ),
                        Member("somar", "method", "int", "public", (("outro", "int"),)),
                        Member("ecoar", "method", "String", "public", (("texto", "String"),)),
                    ),
                ),
            ),
            relationships=(),
            requirements=(),
        )

        report = ContractValidator(JavaToolchain(FIXTURE)).validate(contract, FIXTURE)

        self.assertTrue(report.valid, report.issues)

    def test_validator_accepts_constructor_with_multiple_parameters(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Veiculo.java").write_text(
                "public class Veiculo { public Veiculo(int a, int b, Double c) {} }\n",
                encoding="utf-8",
            )
            contract = Specification(
                units=(
                    Unit(
                        name="Veiculo",
                        kind="class",
                        members=(
                            Member(
                                "Veiculo",
                                "constructor",
                                "Veiculo",
                                "public",
                                (("a", "int"), ("b", "int"), ("c", "Double")),
                            ),
                        ),
                    ),
                ),
                relationships=(),
                requirements=(),
            )

            report = ContractValidator(JavaToolchain(root)).validate(contract, root)

            self.assertTrue(report.valid, report.issues)


    def test_inspect_uses_the_configured_timeout(self) -> None:
        toolchain = JavaToolchain(FIXTURE, inspect_timeout_s=7)
        self.assertTrue(toolchain.compile([Path("Calculadora.java")]).success)
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with mock.patch(
            "java_assistant.java.toolchain.subprocess.run", return_value=completed
        ) as run:
            toolchain.inspect("Calculadora")
            self.assertEqual(7, run.call_args.kwargs["timeout"])
            toolchain.inspect("Calculadora", timeout_s=2)
            self.assertEqual(2, run.call_args.kwargs["timeout"])

    def test_validator_keeps_static_in_the_contract_signature(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Main.java").write_text(
                "public class Main { public static void main(String[] args) {} }\n",
                encoding="utf-8",
            )

            def contract(modifiers: tuple[str, ...]) -> Specification:
                return Specification(
                    units=(
                        Unit(
                            name="Main",
                            kind="class",
                            members=(
                                Member(
                                    "main",
                                    "method",
                                    "void",
                                    "public",
                                    (("args", "String[]"),),
                                    modifiers=modifiers,
                                ),
                            ),
                        ),
                    ),
                    relationships=(),
                    requirements=(),
                )

            toolchain = JavaToolchain(root)
            self.assertTrue(
                ContractValidator(toolchain).validate(contract(("static",)), root).valid
            )
            report = ContractValidator(toolchain).validate(contract(()), root)
            self.assertFalse(report.valid)
            self.assertIn("main", " ".join(report.issues))


if __name__ == "__main__":
    unittest.main()
