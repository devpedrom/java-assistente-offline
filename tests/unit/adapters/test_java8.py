import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.adapters.java8 import Java8Adapter
from java_assistant.core.spec import Member, Relationship, Specification, Unit
from java_assistant.java.toolchain import JavaToolchain


def spec_with(*units: Unit, relationships: tuple[Relationship, ...] = ()) -> Specification:
    return Specification(units=units, relationships=relationships, requirements=())


def conta() -> Specification:
    return spec_with(
        Unit(
            "Conta",
            "class",
            (
                Member("saldo", "field", "double", "private"),
                Member("Conta", "constructor", "Conta", "public"),
                Member("depositar", "method", "void", "public", (("valor", "double"),)),
            ),
        )
    )


class FakeToolchain:
    def __init__(self, outputs: dict[str, str | None]) -> None:
        self.outputs = outputs
        self.inspected: list[str] = []

    def inspect(self, symbol: str, timeout_s: int = 10) -> subprocess.CompletedProcess[str]:
        self.inspected.append(symbol)
        output = self.outputs.get(symbol)
        if output is None:
            return subprocess.CompletedProcess([], 1, "", "not found")
        return subprocess.CompletedProcess([], 0, output, "")


class UnitContractTests(unittest.TestCase):
    def test_lists_declarations_and_required_header(self) -> None:
        spec = spec_with(
            Unit("Base", "class", ()),
            Unit(
                "Conta",
                "class",
                (Member("saldo", "field", "double", "private"),),
            ),
            Unit("Pagavel", "interface", ()),
            relationships=(
                Relationship("Base", "Conta", "inheritance", 0.98),
                Relationship("Pagavel", "Conta", "implements", 0.98),
                Relationship("Base", "Outra", "inheritance", 0.98),
            ),
        )
        text = Java8Adapter().unit_contract(spec, spec.units[1])

        self.assertIn("private double saldo;", text)
        self.assertIn("public class Conta extends Base implements Pagavel", text)
        self.assertIn('"parent":"Base","child":"Conta"', text)
        self.assertNotIn("Outra", text)

    def test_abstract_unit_keeps_the_abstract_keyword_in_the_header(self) -> None:
        spec = spec_with(
            Unit("Base", "class", ()),
            Unit("Conta", "class", (), modifiers=("abstract",)),
            relationships=(Relationship("Base", "Conta", "inheritance", 0.98),),
        )
        text = Java8Adapter().unit_contract(spec, spec.units[1])

        self.assertIn("public abstract class Conta extends Base", text)

    def test_ignores_low_confidence_relations_in_the_header(self) -> None:
        spec = spec_with(
            Unit("Base", "class", ()),
            Unit("Conta", "class", ()),
            relationships=(Relationship("Base", "Conta", "inheritance", 0.8),),
        )
        text = Java8Adapter().unit_contract(spec, spec.units[1])

        self.assertNotIn("CABEÇALHO OBRIGATÓRIO", text)


class PromptTests(unittest.TestCase):
    def test_prompt_keeps_sections_and_asks_for_exactly_one_public_type(self) -> None:
        adapter = Java8Adapter()
        messages = adapter.build_unit_prompt(
            spec=conta(),
            unit=conta().units[0],
            rules=(),
            sections={
                "protocol": "P",
                "criteria": "C",
                "parents": "PAIS",
                "user_request": "crie Conta",
            },
        )

        self.assertEqual(["system", "user"], [message.role for message in messages])
        self.assertIn("P", messages[0].content)
        self.assertIn("C", messages[0].content)
        self.assertIn("private double saldo;", messages[0].content)
        self.assertIn("PAIS", messages[0].content)
        self.assertIn("SOMENTE Conta.java", messages[1].content)
        self.assertIn("crie Conta", messages[1].content)

    def test_prompt_uses_the_spec_target_section_when_present(self) -> None:
        messages = Java8Adapter().build_unit_prompt(
            spec=conta(),
            unit=conta().units[0],
            rules=(),
            sections={"spec_target": "ALVO"},
        )

        self.assertIn("ALVO", messages[0].content)


class ParseTests(unittest.TestCase):
    unit = Unit("Veiculo", "class", ())

    def test_accepts_plain_fenced_and_write_block(self) -> None:
        adapter = Java8Adapter()
        plain = "public class Veiculo {}"

        self.assertEqual(plain + "\n", adapter.parse_unit_source(plain, self.unit))
        self.assertEqual(
            plain + "\n", adapter.parse_unit_source(f"```java\n{plain}\n```", self.unit)
        )
        self.assertEqual(
            "public interface Pagavel {}\n",
            adapter.parse_unit_source(
                '<write_file path="Pagavel.java">\npublic interface Pagavel {}\n'
                "</write_file>\n<compile_java />",
                Unit("Pagavel", "interface", ()),
            ),
        )

    def test_rejects_wrong_multiple_or_missing_public_type(self) -> None:
        adapter = Java8Adapter()

        for reply in (
            "public class Carro {}",
            "public class Veiculo {}\npublic class Carro {}",
            "class Veiculo {}",
        ):
            with self.assertRaises(ValueError):
                adapter.parse_unit_source(reply, self.unit)

    def test_rejects_a_public_type_of_the_wrong_kind(self) -> None:
        with self.assertRaises(ValueError):
            Java8Adapter().parse_unit_source("public interface Veiculo {}", self.unit)

    def test_rejects_incomplete_blocks_and_mixed_actions(self) -> None:
        adapter = Java8Adapter()

        for reply in (
            '<write_file path="Veiculo.java">\npublic class Veiculo {}',
            "```java\npublic class Veiculo {}",
            "public class Veiculo {}\n<compile_java />",
        ):
            with self.assertRaises(ValueError):
                adapter.parse_unit_source(reply, self.unit)


class InspectionTests(unittest.TestCase):
    def test_structural_issues_reuses_the_compiled_contract_check(self) -> None:
        spec = conta()
        complete = FakeToolchain(
            {
                "Conta": "public class Conta { private double saldo; "
                "public Conta(); public void depositar(double); }"
            }
        )
        incomplete = FakeToolchain({"Conta": "public class Conta { }"})

        adapter = Java8Adapter()

        self.assertEqual((), adapter.structural_issues(spec, complete))
        issues = adapter.structural_issues(spec, incomplete)
        self.assertTrue(any("saldo" in issue for issue in issues))
        self.assertTrue(any("depositar" in issue for issue in issues))
        self.assertNotIn("compile", " ".join(complete.inspected))

    def test_structural_issues_checks_declared_inheritance_and_implements(self) -> None:
        spec = spec_with(
            Unit("Base", "class", ()),
            Unit("Pagavel", "interface", ()),
            Unit("Conta", "class", ()),
            relationships=(
                Relationship("Base", "Conta", "inheritance", 0.98),
                Relationship("Pagavel", "Conta", "implements", 0.98),
            ),
        )
        adapter = Java8Adapter()

        correct = FakeToolchain(
            {
                "Base": "public class Base { }",
                "Pagavel": "public interface Pagavel { }",
                "Conta": "public class Conta extends Base implements Pagavel { }",
            }
        )
        wrong = FakeToolchain(
            {
                "Base": "public class Base { }",
                "Pagavel": "public interface Pagavel { }",
                "Conta": "public class Conta { }",
            }
        )

        self.assertEqual((), adapter.structural_issues(spec, correct))
        issues = adapter.structural_issues(spec, wrong)
        self.assertTrue(any("extends Base" in issue for issue in issues))
        self.assertTrue(any("implements Pagavel" in issue for issue in issues))

    def test_structural_issues_accepts_package_members_and_abstract_units(self) -> None:
        package_spec = spec_with(
            Unit(
                "Conta",
                "class",
                (
                    Member("saldo", "field", "double", "package"),
                    Member("depositar", "method", "void", "package"),
                ),
            )
        )
        abstract_spec = spec_with(
            Unit(
                "Base",
                "class",
                (Member("pagar", "method", "void", "public"),),
                modifiers=("abstract",),
            )
        )
        adapter = Java8Adapter()

        self.assertEqual(
            (),
            adapter.structural_issues(
                package_spec,
                FakeToolchain(
                    {"Conta": "public class Conta { double saldo; void depositar(); }"}
                ),
            ),
        )
        self.assertEqual(
            (),
            adapter.structural_issues(
                abstract_spec,
                FakeToolchain(
                    {
                        "Base": "public abstract class Base { "
                        "public abstract void pagar(); }"
                    }
                ),
            ),
        )

    def test_repair_target_returns_the_java_file_of_the_first_error(self) -> None:
        adapter = Java8Adapter()
        diagnostics = "/projeto/Conta.java:12: error: cannot find symbol\n"

        self.assertEqual("Conta", adapter.repair_target(diagnostics))
        self.assertIsNone(adapter.repair_target("erro sem arquivo java"))
        self.assertIsNone(adapter.repair_target("/projeto/Conta.class:12: error"))

    def test_diagnostic_hint_names_the_java8_fix(self) -> None:
        adapter = Java8Adapter()

        hint = adapter.diagnostic_hint(
            "error: incompatible types: int cannot be converted to Double"
        )

        self.assertIn("(double)", hint)
        self.assertIn(
            "construtor",
            adapter.diagnostic_hint(
                "error: no suitable constructor found for Carro(int,int,Double)"
            ),
        )
        self.assertEqual("", adapter.diagnostic_hint("error: something else"))

    def test_entry_point_requires_a_static_main(self) -> None:
        adapter = Java8Adapter()
        static_main = spec_with(
            Unit("App", "class", (Member("main", "method", "void", "public", modifiers=("static",)),))
        )
        instance_main = spec_with(
            Unit("App", "class", (Member("main", "method", "void", "public"),))
        )

        self.assertEqual("App", adapter.entry_point(static_main))
        self.assertIsNone(adapter.entry_point(instance_main))
        self.assertIsNone(adapter.entry_point(spec_with(Unit("Vazio", "class", ()))))


class MatcherTests(unittest.TestCase):
    def test_matchers_find_only_the_requested_constructs(self) -> None:
        matchers = Java8Adapter().matchers()

        self.assertTrue(matchers.factor(1.5).search("total * 1.5"))
        self.assertIsNone(matchers.factor(1.5).search("total * 1.55"))
        self.assertIsNone(matchers.factor(2.0).search("total * 2.5"))
        self.assertTrue(matchers.factor(2.0).search("total * (1 + 100/100)"))
        self.assertTrue(matchers.factor(1.5).search("total * (1.0 + 50.0 / 100)"))
        self.assertTrue(matchers.factor(0.5).search("total * (1 - 50/100)"))
        self.assertIsNone(matchers.factor(0.75).search("total * (1 - 50/100)"))
        self.assertIsNone(matchers.factor(2.0).search("total * (1 + 100/1000)"))
        self.assertTrue(
            matchers.upper_bound_guard().search("if (valor > limite) throw new IllegalArgumentException();")
        )
        self.assertIsNone(matchers.upper_bound_guard().search("if (valor > limite) { }"))
        self.assertTrue(matchers.super_call("total").search("super.total()"))
        self.assertTrue(
            matchers.arithmetic_on_super("total").search("return super.total() * 0.5;")
        )
        self.assertTrue(
            matchers.arithmetic_on_super("total").search(
                "double base = super.total();\nbase *= 0.9;\nreturn base;"
            )
        )
        self.assertTrue(
            matchers.arithmetic_on_super("total").search(
                "Double base = super.total();\n"
                "if (this.flag) {\n    base *= 2.0;\n}\nreturn base;"
            )
        )
        self.assertTrue(
            matchers.arithmetic_on_super("total").search(
                "Double base = super.total();\nbase = base * 2.0;\nreturn base;"
            )
        )
        self.assertIsNone(
            matchers.arithmetic_on_super("total").search(
                "double base = super.total();\nreturn base;"
            )
        )
        self.assertIsNone(matchers.super_call("total").search("super.totalizado()"))


class ClasspathTests(unittest.TestCase):
    def test_classpath_args_are_empty_by_default_and_joined_otherwise(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Main.java").write_text("class Main {}", encoding="utf-8")
            toolchain = JavaToolchain(root, classpath=(root / "a.jar", root / "b.jar"))

            args = toolchain.classpath_args()

        self.assertEqual("-cp", args[0])
        self.assertIn("a.jar", args[1])
        self.assertIn("b.jar", args[1])
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Main.java").write_text("class Main {}", encoding="utf-8")
            self.assertEqual((), JavaToolchain(root).classpath_args())


if __name__ == "__main__":
    unittest.main()
