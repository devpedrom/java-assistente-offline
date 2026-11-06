import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.java import judge
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.model.client import ModelReply
from java_assistant.pdf.extract import PdfEvidence
from java_assistant.uml.extract import UmlExtractor


TEXT = """class Conta
+ Conta(base: Double)
+ total(): Double
Regra: total retorna a base com aumento de 25%.
"""


class ProposalModel:
    def __init__(self, cases):
        self.cases = cases

    def complete(self, messages, **kwargs):
        return ModelReply(json.dumps({"cases": self.cases}))


CASE = {"class_name": "Conta", "constructor_args": [100.0], "method": "total",
        "args": [], "expected": 125.0, "evidence": "aumento de 25%"}


class JudgeTests(unittest.TestCase):
    def test_single_json_fence_is_parsed_without_accepting_surrounding_prose(self):
        class FencedModel:
            prefix = ""
            def complete(self, messages, **kwargs):
                return ModelReply(self.prefix + '```json\n' + json.dumps({"cases": [CASE]}) + '\n```')
        model = FencedModel()
        instance = judge.Judge(None, model)
        self.assertEqual(1, len(instance.build_cases(self.contract(), TEXT)))
        model.prefix = "Texto fora do JSON.\n"
        self.assertEqual([], instance.build_cases(self.contract(), TEXT))

    def test_proposals_over_the_cpu_budget_are_not_silently_executed(self):
        instance = judge.Judge(None, ProposalModel([CASE] * 4))
        self.assertEqual([], instance.build_cases(self.contract(), TEXT))
        self.assertTrue(instance.unverified)

    def test_classes_without_a_proposed_case_are_explicitly_unverified(self):
        instance = judge.Judge(None, ProposalModel([CASE]))
        instance.build_cases(self.contract(TEXT + "\nclass Outra\n+ total(): Double"), TEXT)
        self.assertTrue(any("Outra" in item for item in instance.unverified))

    def contract(self, text=TEXT):
        return UmlExtractor().extract(PdfEvidence(text, "texto", ()))

    def test_cases_are_inferred_and_require_a_real_quote_and_known_signature(self):
        for change in ({"method": "inventado"}, {"evidence": "regra inventada"},
                       {"constructor_args": ["100); System.exit(0);//"]},
                       {"expected": float("nan")}, {"class_name": "../Conta"}):
            with self.subTest(change=change):
                instance = judge.Judge(None, ProposalModel([{**CASE, **change}]))
                self.assertEqual([], instance.build_cases(self.contract(), TEXT))
                self.assertTrue(instance.unverified)

    def test_missing_information_is_unverified_not_passed(self):
        instance = judge.Judge(None, ProposalModel([]))
        cases = instance.build_cases(self.contract(), TEXT)
        report = instance.run(cases)
        self.assertEqual((), report.passed)
        self.assertTrue(report.unverified)

    def run_case(self, source, text=TEXT, case=CASE):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Conta.java").write_text(source, encoding="utf-8")
            toolchain = JavaToolchain(root)
            self.addCleanup(toolchain.close)
            self.assertTrue(toolchain.compile([Path("Conta.java")]).success)
            instance = judge.Judge(toolchain, ProposalModel([case]))
            cases = instance.build_cases(self.contract(text), text)
            self.assertEqual(1, len(cases), instance.unverified)
            report = instance.run(cases)
            self.assertEqual(["Conta.java"], [p.name for p in root.iterdir()])
            return report

    def test_correct_result_passes_and_wrong_formula_fails(self):
        source = "public class Conta { private Double b; public Conta(Double b){this.b=b;} public Double total(){return b * %s;} }"
        self.assertTrue(self.run_case(source % "1.25").passed)
        self.assertTrue(self.run_case(source % "1.5").failed)

    def test_primitive_return_is_rejected_even_when_value_matches(self):
        report = self.run_case("public class Conta { public Conta(Double b){} public double total(){return 125.0;} }")
        self.assertTrue(report.failed)
        self.assertIn("total", report.failed[0])

    def test_boxed_method_argument_does_not_select_primitive_overload(self):
        text = "class Conta\n+ total(valor: Double): Double\nRegra: total devolve 125."
        case = {**CASE, "constructor_args": [], "args": [100.0], "evidence": "total devolve 125"}
        source = "public class Conta { public Double total(Double b){return 999.0;} public Double total(double b){return 125.0;} }"
        self.assertTrue(self.run_case(source, text, case).failed)

    def test_boxed_constructor_does_not_select_primitive_overload(self):
        source = "public class Conta { Double b; public Conta(Double b){this.b=999.0;} public Conta(double b){this.b=125.0;} public Double total(){return b;} }"
        self.assertTrue(self.run_case(source).failed)

    def test_missing_constructor_parameters_is_rejected(self):
        report = self.run_case("public class Conta { public Conta(){} public Double total(){return 125.0;} }")
        self.assertTrue(report.failed)
        self.assertIn("Conta", report.failed[0])

    def test_expected_exception_is_actually_required(self):
        case = {**CASE, "constructor_args": [-1.0], "method": None, "expected": None,
                "exception": "IllegalArgumentException", "evidence": "nunca pode ser negativo"}
        text = TEXT + "O valor nunca pode ser negativo."
        valid = "public class Conta { public Conta(Double b){if(b<0)throw new IllegalArgumentException();} public Double total(){return 0.0;} }"
        self.assertTrue(self.run_case(valid, text, case).passed)
        self.assertTrue(self.run_case(valid.replace("if(b<0)", "if(b>0)"), text, case).failed)

    def test_setup_call_can_observe_void_state_change(self):
        text = TEXT + "\n+ render(): void\nRegra: render aumenta a base em 25%."
        case = {**CASE, "steps": [{"method": "render", "args": []}], "evidence": "render aumenta a base em 25%"}
        source = "public class Conta { private Double b; public Conta(Double b){this.b=b;} public void render(){b*=1.25;} public Double total(){return b;} }"
        self.assertTrue(self.run_case(source, text, case).passed)

    def test_integer_results_do_not_use_float_tolerance(self):
        text = "class Conta\n+ total(): Long\nRegra: total devolve 1000000000000000000."
        case = {**CASE, "constructor_args": [], "expected": 1000000000000000000,
                "evidence": "total devolve 1000000000000000000"}
        source = "public class Conta { public Long total(){return 1000000000000000001L;} }"
        self.assertTrue(self.run_case(source, text, case).failed)

    def test_subclass_rule_is_checked_with_composed_parent_effect(self):
        text = "class Base\n+ Base(valor: Double)\n+ total(): Double\nclass Conta\nherda de: Base\n+ Conta(valor: Double)\n+ total(): Double\nRegra: valor base sofre redução de 10%, depois redução pela metade."
        case = {**CASE, "constructor_args": [500.0], "expected": 225.0,
                "evidence": "redução de 10%, depois redução pela metade"}
        source = "class Base { double b; public Base(Double b){this.b=b;} public Double total(){return b*.9;} } public class Conta extends Base { public Conta(Double b){super(b);} public Double total(){return super.total()*.5;} }"
        self.assertTrue(self.run_case(source, text, case).passed)
