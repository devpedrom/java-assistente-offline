from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.java.toolchain import JavaToolchain
from java_assistant.java.validator import ContractValidator
from java_assistant.uml.models import JavaClass, JavaContract, JavaMember


FIXTURE = Path(__file__).parents[1] / "fixtures" / "java" / "simple"


class JavaToolchainIntegrationTests(unittest.TestCase):
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
        contract = JavaContract(
            classes=(
                JavaClass(
                    name="Calculadora",
                    fields=(JavaMember("valor", "int", "private"),),
                    methods=(
                        JavaMember("Calculadora", "Calculadora", "public", (("valor", "int"),)),
                        JavaMember("somar", "int", "public", (("outro", "int"),)),
                        JavaMember("ecoar", "String", "public", (("texto", "String"),)),
                    ),
                ),
            ),
            relationships=(),
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
            contract = JavaContract(
                classes=(
                    JavaClass(
                        name="Veiculo",
                        fields=(),
                        methods=(
                            JavaMember(
                                "Veiculo",
                                "Veiculo",
                                "public",
                                (("a", "int"), ("b", "int"), ("c", "Double")),
                            ),
                        ),
                    ),
                ),
                relationships=(),
            )

            report = ContractValidator(JavaToolchain(root)).validate(contract, root)

            self.assertTrue(report.valid, report.issues)


if __name__ == "__main__":
    unittest.main()
