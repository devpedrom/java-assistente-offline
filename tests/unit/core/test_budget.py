from pathlib import Path
from types import MappingProxyType
import unittest

from java_assistant.core.budget import (
    ContextBudget,
    ContextBudgetError,
    apply_budget,
)
from java_assistant.criteria import build_context


def budget(context_tokens: int, sections: dict[str, int]) -> ContextBudget:
    return ContextBudget(
        context_tokens=context_tokens,
        output_tokens=0,
        reserved_tokens=0,
        chars_per_token=1.0,
        sections=MappingProxyType(sections),
    )


def all_sections(ceiling: int = 100) -> dict[str, int]:
    return {
        name: ceiling
        for name in (
            "protocol",
            "criteria",
            "spec_target",
            "user_request",
            "rules",
            "parents",
            "pdf_excerpt",
            "memory",
        )
    }


class BudgetTests(unittest.TestCase):
    def test_contract_and_confirmed_requirements_borrow_optional_context_without_truncation(self) -> None:
        target = "assinatura obrigatoria\n" + "regra confirmada\n" * 8 + "REGRA FINAL"
        result = apply_budget(
            {"spec_target": target, "memory": "historico"},
            budget(220, {"spec_target": 10, "memory": 100}),
        )
        self.assertEqual(target, result.sections["spec_target"])
        self.assertNotIn("spec_target", result.truncated)
        self.assertEqual(("memory",), result.omitted)

    def test_contract_larger_than_the_whole_window_aborts_instead_of_losing_requirements(self) -> None:
        with self.assertRaises(ContextBudgetError):
            apply_budget({"spec_target": "x" * 501}, budget(500, {"spec_target": 10}))

    def test_default_4096_budget_fits_all_sections_and_preserves_priority(self) -> None:
        sections = {name: name * 10 for name in all_sections()}

        result = apply_budget(sections, ContextBudget())

        self.assertEqual((), result.omitted)
        self.assertEqual((), result.truncated)
        self.assertEqual(3328, result.available_tokens)
        self.assertEqual(set(sections), set(result.sections))

    def test_overflow_drops_lowest_priority_first(self) -> None:
        sections = {name: name * 5 for name in all_sections()}

        one = apply_budget(sections, budget(700, all_sections()))
        three = apply_budget(sections, budget(500, all_sections()))

        self.assertEqual(("memory",), one.omitted)
        self.assertEqual(("memory", "pdf_excerpt", "parents"), three.omitted)
        self.assertNotIn("memory", three.sections)
        self.assertNotIn("pdf_excerpt", three.sections)
        self.assertNotIn("parents", three.sections)
        for protected in ("protocol", "criteria", "spec_target", "user_request"):
            self.assertIn(protected, three.sections)

    def test_criteria_overflow_aborts_with_actionable_message(self) -> None:
        sections = {"criteria": "x" * 40, "memory": "m"}
        ceilings = {"criteria": 10, "memory": 100}

        with self.assertRaises(ContextBudgetError) as caught:
            apply_budget(sections, budget(500, ceilings))

        message = str(caught.exception)
        self.assertIn("critérios", message)
        self.assertIn("Reduza", message)
        self.assertIn("CRITERIOS_GERAIS.md", message)

    def test_truncation_cuts_on_line_boundary_and_reports_count(self) -> None:
        text = "linha1\nlinha2\nlinha3"
        sections = {"memory": text}

        result = apply_budget(sections, budget(500, {"memory": 10}))

        self.assertEqual(("memory",), result.truncated)
        self.assertTrue(result.sections["memory"].startswith("linha1\n"))
        self.assertIn("[... truncado: 14 caracteres omitidos]", result.sections["memory"])
        self.assertNotIn("linha2", result.sections["memory"])

    def test_shipped_criteria_template_fits_the_default_ceiling(self) -> None:
        template = (
            Path(__file__).parents[3] / "instructions" / "CRITERIOS_GERAIS.md"
        ).read_text(encoding="utf-8")

        result = apply_budget({"criteria": template}, ContextBudget())

        self.assertEqual((), result.truncated)
        self.assertEqual(template, result.sections["criteria"])

    def test_protected_sections_over_budget_fail_loudly(self) -> None:
        ceilings = {"criteria": 150, "memory": 100}

        with self.assertRaises(ContextBudgetError) as caught:
            apply_budget(
                {"criteria": "x", "memory": "m"}, budget(100, ceilings)
            )

        self.assertIn("obrigatórias", str(caught.exception))

    def test_user_request_over_ceiling_is_kept_but_reported(self) -> None:
        request = "x" * 40

        result = apply_budget(
            {"user_request": request}, budget(500, {"user_request": 10})
        )

        self.assertEqual(request, result.sections["user_request"])
        self.assertEqual(("user_request",), result.truncated)

    def test_build_context_still_places_request_last(self) -> None:
        ceilings = {
            "criteria": 10,
            "spec_target": 10,
            "pdf_excerpt": 10,
            "memory": 10,
            "parents": 10,
            "user_request": 10,
        }
        messages = build_context(
            criteria="crit",
            contract="contrato",
            source_text="pdf",
            memory_summary="MEMORIA ANTIGA",
            relevant_files={"A.java": "class A {}"},
            user_request="pedido atual",
            budget=budget(40, ceilings),
        )

        self.assertEqual(["system", "user"], [message.role for message in messages])
        self.assertEqual("pedido atual", messages[-1].content)
        self.assertNotIn("MEMORIA ANTIGA", messages[0].content)


if __name__ == "__main__":
    unittest.main()
