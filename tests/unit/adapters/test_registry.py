from pathlib import Path
import unittest

from java_assistant.adapters import adapter_ids, resolve_adapter
from java_assistant.adapters.base import CompileResult as BaseCompileResult
from java_assistant.adapters.stub import StubToolchain
from java_assistant.core.spec import Member, Specification, Unit
from java_assistant.java.toolchain import CompileResult as JavaCompileResult


def sample() -> Specification:
    return Specification(
        units=(
            Unit(
                "Item",
                "class",
                (Member("id", "field", "int", "private"),),
            ),
        ),
        relationships=(),
        requirements=(),
    )


class RegistryTests(unittest.TestCase):
    def test_stub_is_hidden_by_default_and_listed_when_allowed(self) -> None:
        self.assertNotIn("stub", adapter_ids())
        self.assertIn("stub", adapter_ids(allow_stub=True))
        with self.assertRaises(ValueError):
            resolve_adapter("stub")
        self.assertEqual("stub", resolve_adapter("stub", allow_stub=True).id)

    def test_unknown_adapter_lists_the_available_ids(self) -> None:
        with self.assertRaises(ValueError) as caught:
            resolve_adapter("python3", allow_stub=True)

        message = str(caught.exception)
        self.assertIn("python3", message)
        self.assertIn("stub", message)

    def test_stub_satisfies_the_protocol_end_to_end(self) -> None:
        adapter = resolve_adapter("stub", allow_stub=True)
        spec = sample()
        unit = spec.units[0]

        messages = adapter.build_unit_prompt(
            spec=spec,
            unit=unit,
            rules=(),
            sections={"protocol": "P", "user_request": "crie Item"},
        )

        self.assertEqual(2, len(messages))
        self.assertEqual("crie Item", messages[-1].content)
        self.assertEqual("class Item", adapter.unit_contract(spec, unit))
        self.assertEqual("conteudo\n", adapter.parse_unit_source("conteudo", unit))
        self.assertEqual((), adapter.structural_issues(spec, StubToolchain()))
        self.assertIsNone(adapter.repair_target("erro"))
        self.assertEqual("", adapter.diagnostic_hint("erro"))
        self.assertEqual("Item", adapter.entry_point(spec))
        matchers = adapter.matchers()
        self.assertTrue(matchers.factor(2.0).search("* 2.0"))
        self.assertTrue(matchers.upper_bound_guard().search("valor > limite"))
        self.assertTrue(matchers.super_call("total").search("super.total()"))
        self.assertTrue(matchers.arithmetic_on_super("total").search("super.total() * 0.5"))

    def test_stub_toolchain_compiles_runs_and_inspects(self) -> None:
        toolchain = StubToolchain()

        compiled = toolchain.compile([Path("Item.txt")])
        run = toolchain.run("Item", 5, stdin="entrada")
        inspected = toolchain.inspect("Item")

        self.assertTrue(compiled.success)
        self.assertEqual("entrada", run.stdout)
        self.assertEqual(0, inspected.returncode)
        self.assertEqual(["Item"], toolchain.runs)

    def test_result_types_are_shared_with_the_java_toolchain(self) -> None:
        self.assertIs(BaseCompileResult, JavaCompileResult)


if __name__ == "__main__":
    unittest.main()
